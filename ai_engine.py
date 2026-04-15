"""
ai_engine.py  —  V2.1 Strategic Auditor (Multi-Provider)
=========================================================
يُرسل بيانات المكتب + نص الخطة الشهرية إلى المزوّد المُختار (Groq أو Gemini)
ويستقبل تقريرًا Auditيًا مقارنًا احترافيًا باللغة العربية.

المزوّد يُحدَّد عبر LLM_PROVIDER في ملف .env:
  LLM_PROVIDER=GROQ    → Llama 3 70B عبر Groq  (الافتراضي)
  LLM_PROVIDER=GEMINI  → Gemini 2.5 Flash (احتياطي)

لا تغييرات على منطق Google Sheets / Drive.
"""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod

import config as cfg
from data_parser import OfficeData, get_task_statistics


# ─── System Instruction: Strategic Auditor Persona ───────────────────────────
_SYSTEM_INSTRUCTION = """
أنت مدقّق استراتيجي متخصص في تقييم الأداء المؤسسي للاتحاد العام لطلبة سوريا.
مهمتك: إعداد تقرير Audit مقارن احترافي شامل باللغة العربية الفصحى ذات الأسلوب الإداري الرسمي.

يجب أن يتضمن كل تقرير الأقسام التالية بالترتيب الآتي:

القسم الأول — الملخص التنفيذي الشامل
اكتب فقرة نثرية متماسكة لا تقل عن سبعة أسطر، تُدمج فيها جميع المعطيات الآتية دون إغفال أيٍّ منها:
  - نظرة عامة على مستوى الأداء الكلي للمكتب خلال الشهر.
  - ملخص تحليلي لأبرز المهام المُنفَّذة والمنهجية المتبعة والقيمة المُضافة لكل منها.
  - التحديات العامة المُبلَّغ عنها وتأثيرها على مسار العمل.
  - الملاحظات الإضافية المُدرجة وما تنطوي عليه من توصيات أو رغبات.
يُحظر في هذا القسم استخدام أي أرقام تقييمية أو رموز تقنية أو بيانات وصفية خاما.
الأسلوب نثري رسمي حصرًا، مع الحرص على تصحيح أي أخطاء إملائية أو لغوية.

القسم الثاني — تقييم المهام المُنفَّذة
أنشئ في هذا القسم حصرًا كتلة JSON واحدة وفق الهيكل الآتي، دون أي نص خارجها:
```json
[
  {
    "task_id": "رقم المهمة",
    "original_name": "اسم المهمة كما وردَ في النموذج",
    "ai_insight": "جملة واحدة بأسلوب الاستشارة الإدارية الرفيعة تدمج الهدف الاستراتيجي والمنهجية والأثر التشغيلي وأي قيود جوهرية في سياق نثري متصل"
  }
]
```
يُحظر تمامًا إدراج أي حقل تقييمي رقمي (impact_score أو ما شابهه) في المخرجات.
يجب تناول كل مهمة مذكورة في البيانات دون استثناء.

القسم الثالث — الاختناقات الإدارية والتحديات
صِف بأسلوب نثري رسمي الإشكاليات المذكورة في حقل إشكاليات كل مهمة، موحِّدًا المتشابه منها وصانِّفًا ما ينفرد بجدة، ومُصنِّفًا الأولوية (عالية / متوسطة / منخفضة) ضمن النص لا في بيانات منفصلة.

القسم الرابع — تحليل المطابقة: الخطة المعتمدة مقابل الإنجاز الفعلي
حلّل بصورة مقارنة تفصيلية:
  أ) نسبة الالتزام بالخطة الشهرية المعتمدة.
  ب) الفجوات التنفيذية: ما خُطِّط له ولم يُنفَّذ.
  ج) الأعمال الاستثنائية: ما نُفِّذ خارج نطاق الخطة.
إذا كان نص الخطة غائبًا، أشر إلى ذلك صراحةً وأجرِ التحليل بناءً على بيانات النموذج وحدها.

قواعد إلزامية مشتركة لجميع الأقسام:
أولًا: اللغة العربية الفصحى ذات الأسلوب الإداري الرسمي في جميع الأقسام النصية دون استثناء.
ثانيًا: يُحظر استخدام أي تنسيق Markdown (نجوم، شرطات، رموز) خارج كتلة JSON في القسم الثاني.
ثالثًا: العناوين تُكتب كنص عادي، مثال: «القسم الأول — الملخص التنفيذي الشامل».
رابعًا: لا يجوز إغفال أي معلومة واردة في البيانات المُدخَلة.
خامسًا: يُحظر تمامًا إدراج أي قيم رقمية تقييمية كالدرجات أو النقاط في أي قسم نصي.
"""


# ─── Prompt Builder (مشترك بين المزوّدَيْن) ───────────────────────────────────
def _build_audit_prompt(office_data: OfficeData, plan_text: str) -> str:
    """
    يُنشئ prompt الAudit المقارن المُرسَل إلى أي مزوّد LLM.
    يضمن إدراج general_challenges و additional_notes بشكل صريح.

    Args:
        office_data: المخرجات المباشرة من data_parser.parse_row().
        plan_text:   النص المستخرج من PDF الخطة الشهرية.

    Returns:
        سلسلة نصية جاهزة للإرسال.
    """
    stats = get_task_statistics(office_data)

    # ── الخطة الشهرية ────────────────────────────────────────────────────────
    if plan_text and plan_text.strip():
        plan_section = (
            "=== نص الخطة الشهرية المعتمدة (مُستخرج من PDF) ===\n"
            f"{plan_text[:6000]}\n"
            + ("[... اقتُصر على الجزء الأول بسبب طول النص ...]\n"
               if len(plan_text) > 6000 else "")
        )
    else:
        plan_section = (
            "=== نص الخطة الشهرية المعتمدة ===\n"
            "[غير متوفر — لم يُرفع ملف PDF أو تعذّرت قراءته]\n"
            "تعليمات: أجرِ الAudit اعتمادًا على بيانات النموذج وحدها، "
            "مع التنبيه صراحةً على غياب الخطة المعتمدة.\n"
        )

    # ── الحقول الختامية الإلزامية ─────────────────────────────────────────────
    general_challenges = office_data.get("general_challenges", "").strip()
    additional_notes   = office_data.get("additional_notes",   "").strip()

    challenges_section = (
        f"=== التحديات العامة المُبلَّغ عنها (حقل إلزامي يجب دمجه في الملخص التنفيذي) ===\n"
        f"{general_challenges if general_challenges else '[لم يُدرج المكتب أي تحديات عامة]'}\n"
    )
    notes_section = (
        f"=== الملاحظات الإضافية (حقل إلزامي يجب دمجه في الملخص التنفيذي) ===\n"
        f"{additional_notes if additional_notes else '[لا توجد ملاحظات إضافية]'}\n"
    )

    # ── بيانات المهام (نسخة نظيفة بدون الحقلين الختاميين — مُدرجان أعلاه صراحةً) ─
    tasks_payload = {
        "office_name":    office_data.get("office_name", ""),
        "submitter":      office_data.get("submitter", ""),
        "target_month":   office_data.get("target_month_name", ""),
        "task_statistics": stats,
        "tasks":          office_data.get("tasks", []),
    }

    return (
        f'أجرِ Auditًا مقارنًا شاملًا لأداء "{office_data.get("office_name", "غير محدد")}"'
        f' خلال شهر {office_data.get("target_month_name", "الشهر الحالي")}.\n\n'
        f"{plan_section}\n"
        "=== بيانات المهام التفصيلية (من النموذج الرقمي) ===\n"
        f"{json.dumps(tasks_payload, ensure_ascii=False, indent=2)}\n\n"
        # ── الحقول ذات الأولوية العالية تأتي آخرًا لضمان أعلى attention weight ──
        f"{challenges_section}\n"
        f"{notes_section}\n"
        "=== تعليمات الإخراج ===\n"
        "أنشئ التقرير الAuditي الكامل وفق الأقسام المحددة في دورك.\n"
        "تذكير حاسم — يجب أن يُدمج الملخص التنفيذي (القسم الأول) كلًّا من:\n"
        "  - التحديات العامة المُبلَّغ عنها أعلاه مباشرةً.\n"
        "  - الملاحظات الإضافية المُدرجة أعلاه مباشرةً.\n"
        "لا يجوز إدراج أي أرقام تقييمية أو درجات في أي قسم نصي.\n"
        "لا يجوز نسخ قيم الحقول الخام (mechanism / description) حرفيًا — حوِّلها إلى تحليل."
    ).strip()


# ─── Abstract Base ────────────────────────────────────────────────────────────
class _BaseAnalyzer(ABC):
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 15.0   # رُفع من 10 ث — قاعدة Exponential Backoff

    @abstractmethod
    def analyze(self, office_data: OfficeData, plan_text: str = "") -> str: ...


# ─── Groq Analyzer — Key-Rotation Edition ───────────────────────────────────
class GroqAnalyzer(_BaseAnalyzer):
    """
    يُغلّف Groq بدور المدقّق الاستراتيجي.
    عند خطأ 429: يُدير المفتاح فورًا ويُعيد المحاولة بدون إضياع attempt.
    """

    def __init__(self) -> None:
        if not cfg.GROQ_API_KEYS:
            raise ValueError(
                "❌ لا يوجد أي مفتاح Groq API.\n"
                "أضف GROQ_API_KEYS=key1,key2 إلى ملف .env\n"
                "احصل على مفاتيحك من: https://console.groq.com/keys"
            )
        try:
            from groq import Groq  # type: ignore
            self._Groq = Groq
        except ImportError:
            raise ImportError("❌ مكتبة groq غير مُثبَّتة. شغّل: pip install groq")

        self._keys       = cfg.GROQ_API_KEYS          # قائمة المفاتيح
        self._key_index  = 0                           # المفتاح النشط حاليًا
        self._client     = self._Groq(api_key=self._keys[0])
        print(f"✅ Groq engine initialized: {cfg.GROQ_MODEL} — {len(self._keys)} key(s) (Strategic Auditor v2.2)")

    def _rotate_key(self) -> bool:
        """
        يُدير إلى المفتاح التالي ويُعيد بناء العميل.
        يُعيد False إذا استُنفدت جميع المفاتيح.
        """
        next_index = self._key_index + 1
        if next_index >= len(self._keys):
            print("❌ All keys exhausted — cannot rotate further.")
            return False
        self._key_index = next_index
        self._client    = self._Groq(api_key=self._keys[next_index])
        print(f"🔄 Key exhausted, switching to next... [Key {next_index + 1}/{len(self._keys)}]")
        return True

    def analyze(self, office_data: OfficeData, plan_text: str = "") -> str:
        """
        يُرسل بيانات المكتب + نص الخطة إلى Groq ويُعيد التقرير الAuditي.
        عند 429: يُدير المفتاح فورًا ويُعيد نفس المحاولة بدون إضياع attempt.
        """
        office_name = office_data.get("office_name", "غير محدد")
        plan_status = "مع خطة PDF" if (plan_text and plan_text.strip()) else "بدون خطة PDF"
        prompt = _build_audit_prompt(office_data, plan_text)

        # عدد المحاولات = MAX_RETRIES × عدد المفاتيح (للتحكم الكامل)
        total_attempts = self.MAX_RETRIES * len(self._keys)
        attempt = 0

        while attempt < total_attempts:
            attempt += 1
            key_label = f"مفتاح {self._key_index + 1}/{len(self._keys)}"
            try:
                print(f"   🤖 [Groq/{key_label}] Audit «{office_name}» [{plan_status}] "
                      f"(محاولة {attempt}/{total_attempts})...")

                response = self._client.chat.completions.create(
                    model=cfg.GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": _SYSTEM_INSTRUCTION},
                        {"role": "user",   "content": prompt},
                    ],
                    temperature=0.3,
                    max_tokens=8192,
                )
                response_text = response.choices[0].message.content.strip()
                print(f"\n--- RAW AI RESPONSE ({office_name}) ---\n"
                      f"{response_text}\n--- END RAW ---\n")
                return response_text

            except Exception as exc:
                err_msg = str(exc)
                is_rate_limit = "rate_limit" in err_msg.lower() or "429" in err_msg

                if is_rate_limit:
                    # تدوير فوري — لا يُحتسب من attempt
                    rotated = self._rotate_key()
                    if rotated:
                        attempt -= 1   # أعد المحاولة بنفس الرقم بالمفتاح الجديد
                        continue
                    # استُنفدت كل المفاتيح — انتظر وخذ إمكانية إعادة تدوير من الأول
                    wait = int(self.RETRY_DELAY * (2 ** min(attempt - 1, 3)))
                    print(f"   ⏳ [All keys exhausted] Backoff", end="", flush=True)
                    for _ in range(wait):
                        time.sleep(1)
                        print(".", end="", flush=True)
                    print(f" {wait}s ✓ — Restarting cycle from first key")
                    self._key_index = 0
                    self._client    = self._Groq(api_key=self._keys[0])
                elif "503" in err_msg or "unavailable" in err_msg.lower():
                    print("   ⏳ [503] Service unavailable", end="", flush=True)
                    for _ in range(5):
                        time.sleep(1)
                        print(".", end="", flush=True)
                    print(" ✓")
                else:
                    print(f"   ⏳ Error: {err_msg[:60]}... retrying...")
                    time.sleep(3)

        return "Analysis currently unavailable"


# ─── Gemini Analyzer (احتياطي) ───────────────────────────────────────────────
class GeminiAnalyzer(_BaseAnalyzer):
    """
    يُغلّف نموذج Gemini 2.5 Flash بدور المدقّق الاستراتيجي.
    يُستخدم احتياطيًا عند ضبط LLM_PROVIDER=GEMINI في .env.
    """

    def __init__(self) -> None:
        if not cfg.GEMINI_API_KEY:
            raise ValueError(
                "❌ مفتاح Gemini API غير محدد.\n"
                "أضف GEMINI_API_KEY إلى ملف .env"
            )
        from google import genai                          # type: ignore
        from google.genai import types as genai_types    # type: ignore

        self._genai_types = genai_types
        self._client = genai.Client(api_key=cfg.GEMINI_API_KEY)
        self._config = genai_types.GenerateContentConfig(
            system_instruction=_SYSTEM_INSTRUCTION,
        )
        print(f"✅ Gemini engine initialized: {cfg.GEMINI_MODEL} (Strategic Auditor v2.1)")

    def analyze(self, office_data: OfficeData, plan_text: str = "") -> str:
        """
        يُرسل بيانات المكتب + نص الخطة إلى Gemini ويُعيد التقرير الAuditي.
        """
        office_name = office_data.get("office_name", "غير محدد")
        plan_status = "مع خطة PDF" if (plan_text and plan_text.strip()) else "بدون خطة PDF"
        prompt = _build_audit_prompt(office_data, plan_text)

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                print(f"   🤖 [Gemini] Audit «{office_name}» [{plan_status}] "
                      f"(محاولة {attempt}/{self.MAX_RETRIES})...")
                response = self._client.models.generate_content(
                    model=cfg.GEMINI_MODEL,
                    contents=prompt,
                    config=self._config,
                )
                return response.text.strip()

            except Exception as exc:
                err_msg = str(exc)
                if attempt < self.MAX_RETRIES:
                    if "503" in err_msg or "Unavailable" in err_msg:
                        print("   ⏳ [503] Service unavailable", end="", flush=True)
                        for _ in range(5):
                            time.sleep(1)
                            print(".", end="", flush=True)
                        print(" ✓")
                    elif "429" in err_msg or "ResourceExhausted" in err_msg:
                        # Exponential Backoff: 15s → 30s → 60s
                        wait = int(self.RETRY_DELAY * (2 ** (attempt - 1)))
                        print(f"   ⏳ [429] Exponential Backoff", end="", flush=True)
                        for _ in range(wait):
                            time.sleep(1)
                            print(".", end="", flush=True)
                        print(f" {wait}s ✓")
                    else:
                        print(f"   ⏳ Error: {err_msg[:40]}... retrying...")
                        time.sleep(2)
                    continue

        return "Analysis currently unavailable"


# ─── Factory: يُعيد المحلّل الصحيح بناءً على LLM_PROVIDER ───────────────────
def get_analyzer() -> _BaseAnalyzer:
    """
    المدخل الوحيد لبقية الكود.

    الاستخدام:
        from ai_engine import get_analyzer
        analyzer = get_analyzer()
        report  = analyzer.analyze(office_data, plan_text)
    """
    provider = cfg.LLM_PROVIDER
    if provider == "GROQ":
        return GroqAnalyzer()
    elif provider == "GEMINI":
        return GeminiAnalyzer()
    else:
        raise ValueError(
            f"❌ مزوّد LLM غير معروف: '{provider}'\n"
            "القيم المقبولة في .env: GROQ | GEMINI"
        )


# ─── Per-Section System Instructions ─────────────────────────────────────────
# NOTE: Instructions are in English to maximize LLM reasoning.
#       Each section enforces Arabic-language output for the report.
_SECTION_INSTRUCTIONS: dict[str, str] = {

    "summary": """
You are a senior strategic auditor. Your sole task: write Section 1 — the Comprehensive Executive Summary.

Produce a single cohesive prose paragraph (minimum 7 lines) synthesizing ALL of the following:
  - An overview of the office's overall performance level for the month.
  - An analytical summary of key tasks: methodology and value delivered by each.
  - General challenges reported and their impact on work continuity.
  - Additional notes/observations and any embedded recommendations.

MANDATORY RULES:
  - IMPORTANT: You MUST generate the final analysis/response in ARABIC only. Use a professional, executive tone.
  - No English in the output.
  - No Markdown formatting (no asterisks, dashes, bullets) and no numerical scores.
  - One continuous prose paragraph only — no section headings.
  - Do NOT copy raw field values verbatim — synthesize into analysis.
""",

    "tasks": """
You are a senior management consultant. Your sole task: produce a JSON array analyzing each executed task.

Output exactly one JSON block. No text before or after it:
```json
[
  {
    "task_id": "task number (1, 2, 3...)",
    "original_name": "task name exactly as it appears in the data",
    "ai_insight": "One cohesive sentence in McKinsey consulting style organically merging: strategic objective + methodology + operational impact + any constraints forming essential context"
  }
]
```

Quality criteria for each ai_insight:
  1. Exactly ONE continuous sentence — no mid-sentence periods, no dashes, no internal bullets.
  2. Organic fusion: value and challenges woven into one narrative, not listed separately.
  3. Vary sentence structure: avoid starting consecutive insights with the same verb.
  4. Use management consulting vocabulary: operational efficiency, institutional readiness, structural capacity.
  5. No verbatim copying: transform raw field data into insight.

Example of the required quality:
  "تُعزّز هذه المبادرة منظومة التواصل المؤسسي مع الكوادر التطوعية السابقة، مستثمِرةً الإرث العلائقي للمكتب في بناء شبكة دعم مستدامة، في ظل غياب قاعدة بيانات مُحكَمة تُعيق استهداف الكفاءات المناسبة."

MANDATORY TECHNICAL RULES:
  - IMPORTANT: You MUST generate the final analysis/response in ARABIC only. Use a professional, executive tone.
  - No English in the output.
  - No fields other than task_id, original_name, ai_insight.
  - Cover every task in the data without exception.
  - task_id: Arabic numerals only (1, 2, 3...) with no extra text.
  - Pure JSON output — no markdown prose outside the JSON block.
  - The VERY LAST character of your response MUST be ] — never stop before the array is closed.
""",

    "audit": """
You are a senior strategic auditor. Your sole task: write Section 4 — Plan vs. Actual Compliance Analysis.

Conduct a detailed comparative analysis covering:
  A) Degree of adherence to the approved monthly plan.
  B) Execution gaps: what was planned but not carried out.
  C) Exceptional work: what was executed outside the plan scope.

If plan text is absent, state this explicitly and analyze based solely on form data.

MANDATORY RULES:
  - IMPORTANT: You MUST generate the final analysis/response in ARABIC only. Use a professional, executive tone.
  - No English in the output.
  - No Markdown formatting and no numerical scores.
  - Do NOT repeat task data verbatim — deliver comparative analysis.
""",

    "challenges": """
You are a senior strategic auditor. Your sole task: write Section 3 — Administrative Bottlenecks and Challenges.

In formal prose, describe the issues reported in each task's issues field, consolidating similar ones
and classifying priority (high / medium / low) within the narrative, not as separate metadata.
Integrate general challenges and additional notes into the analysis context.

MANDATORY RULES:
  - IMPORTANT: You MUST generate the final analysis/response in ARABIC only. Use a professional, executive tone.
  - No English in the output.
  - No Markdown formatting and no numerical scores.
  - Do NOT copy issue text verbatim — reframe in a unified analytical narrative.
""",
}


# ─── Per-Section Prompt Builder ───────────────────────────────────────────────
def _build_section_prompt(
    section: str,
    office_data: OfficeData,
    plan_text: str,
) -> str:
    """بيانات مُركَّزة لكل خيط — نفس البيانات، تعليمات الإخراج مختلفة."""
    import json
    from data_parser import get_task_statistics

    stats = get_task_statistics(office_data)

    plan_block = (
        f"=== نص الخطة الشهرية المعتمدة ===\n{plan_text[:6000]}\n"
        if plan_text and plan_text.strip()
        else "=== الخطة الشهرية ===\n[غير متوفرة]\n"
    )
    general_challenges = office_data.get("general_challenges", "") or "[لم يُدرج]"
    additional_notes   = office_data.get("additional_notes",   "") or "[لا توجد]"

    payload = {
        "office_name":     office_data.get("office_name", ""),
        "submitter":       office_data.get("submitter", ""),
        "target_month":    office_data.get("target_month_name", ""),
        "task_statistics": stats,
        "tasks":           office_data.get("tasks", []),
    }

    return (
        f'أجرِ Auditًا مقارنًا شاملًا لأداء "{office_data.get("office_name", "")}"'
        f' خلال شهر {office_data.get("target_month_name", "الشهر الحالي")}.\n\n'
        f"{plan_block}\n"
        f"=== بيانات المهام التفصيلية ===\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n\n"
        f"=== التحديات العامة (إلزامي) ===\n{general_challenges}\n\n"
        f"=== الملاحظات الإضافية (إلزامي) ===\n{additional_notes}\n\n"
        f"المطلوب منك الآن: أنتِج {section} فقط وفق التعليمات في دورك."
    ).strip()


# ─── Parallel Orchestrator ────────────────────────────────────────────────────
class ParallelOrchestrator:
    """
    يُشغّل 4 خيوط متوازية لكل مكتب، كل خيط يُنتج قسمًا واحدًا:
      summary    → llama-3.3-70b-versatile (Groq)
      tasks      → llama-3.1-8b-instant    (Groq)
      audit      → gemini-2.5-flash        (Gemini API)
      challenges → gemma-4-27b-it          (Gemini API)

    عند 429: تدوير فوري للمفاتيح → عند استنفادها: Gemma 4 Fallback عبر Gemini.
    """

    _SECTION_CFG: dict[str, dict] = {
        "summary":    {"provider": "groq",        "model_attr": "GROQ_MODEL_SUMMARY"},
        "tasks":      {"provider": "groq",        "model_attr": "GROQ_MODEL_TASKS"},
        "audit":      {"provider": "gemini",      "model_attr": "GEMINI_MODEL"},
        "challenges": {"provider": "gemini-gemma4", "model_attr": "GEMINI_MODEL_GEMMA4"},
    }

    def __init__(self) -> None:
        if not cfg.GROQ_API_KEYS:
            raise ValueError("❌ لا يوجد أي مفتاح Groq API. أضف GROQ_API_KEYS إلى .env")

        try:
            from groq import Groq  # type: ignore
            self._Groq = Groq
        except ImportError:
            raise ImportError("❌ pip install groq")

        self._keys      = cfg.GROQ_API_KEYS
        self._key_index = 0                          # مشترك — محمي بـ threading.Lock
        self._lock      = __import__("threading").Lock()

        # Gemini (للAudit المقارن مع PDF)
        self._gemini_client = None
        if cfg.GEMINI_API_KEY:
            try:
                from google import genai  # type: ignore
                self._gemini_client = genai.Client(api_key=cfg.GEMINI_API_KEY)
            except Exception:
                pass   # Gemini غير متوفر — سيُستخدم Groq كـ fallback

        n_keys = len(self._keys)
        print(f"✅ [Orchestrator] Ready — "
              f"4 خيوط | {n_keys} key(s) Groq | "
              f"Gemini={'✅' if self._gemini_client else '⚠️ غير متوفر'}")

    # ── داخلي: Groq call مع key-rotation ────────────────────────────────────
    def _groq_call(self, model: str, system: str, user: str,
                   max_tokens: int = 4096) -> str:
        """
        مُستدعى من الخيوط — يُدير المفتاح عند 429، يعود False عند الاستنفاد.
        """
        total = self.MAX_RETRIES * len(self._keys)
        attempt = 0
        while attempt < total:
            attempt += 1
            with self._lock:
                key   = self._keys[self._key_index]
                k_lbl = f"{self._key_index + 1}/{len(self._keys)}"
            client = self._Groq(api_key=key)
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user",   "content": user},
                    ],
                    temperature=0.3,
                    max_tokens=max_tokens,
                )
                return resp.choices[0].message.content.strip()
            except Exception as exc:
                err = str(exc)
                if "rate_limit" in err.lower() or "429" in err:
                    with self._lock:
                        nxt = self._key_index + 1
                        if nxt < len(self._keys):
                            self._key_index = nxt
                            print(f"\n   🔄 [429] Key exhausted → Key {nxt + 1}/{len(self._keys)}")
                            attempt -= 1   # أعد بنفس الرقم بالمفتاح الجديد
                            continue
                        # كل المفاتيح مجهدة
                    wait = min(15 * (2 ** min(attempt, 3)), 60)
                    print(f"\n   ⏳ [All keys exhausted] Backoff {wait}s", end="", flush=True)
                    for _ in range(wait):
                        time.sleep(1)
                        print(".", end="", flush=True)
                    print(" ✓")
                    with self._lock:
                        self._key_index = 0   # أعد التدوير
                else:
                    time.sleep(3)
        return ""

    MAX_RETRIES: int = 3

    @staticmethod
    def _sanitize(text: str) -> str:
        """يُزيل الأحرف غير الصالحة للإرسال إلى Gemini API."""
        import re
        text = text.encode("utf-8", errors="ignore").decode("utf-8")
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        text = re.sub(r"[\ud800-\udfff]", "", text)    # surrogates
        text = re.sub(r"[\ue000-\uf8ff]", "", text)    # private use area
        return text

    # ── الخيوط 3+4: Gemini / Gemma4 ──────────────────────────────────────────
    def _gemini_call(self, section: str, user_prompt: str) -> str:
        """
        يستدعي Gemini API (مع system_instruction منفصل) أو يسقط إلى Groq.
        النماذج:
          audit      → gemini-2.5-flash
          challenges → gemma-4-27b-it
        """
        if not self._gemini_client:
            return self._groq_call(
                cfg.GROQ_MODEL_FALLBACK,
                _SECTION_INSTRUCTIONS[section],
                user_prompt,
            )

        model     = (cfg.GEMINI_MODEL_GEMMA4 if section == "challenges"
                     else cfg.GEMINI_MODEL)
        sys_inst  = self._sanitize(_SECTION_INSTRUCTIONS[section])
        clean_pmt = self._sanitize(user_prompt)

        for attempt in range(1, 4):
            try:
                from google.genai import types as t  # type: ignore
                out_tokens = 8192 if section == "tasks" else 4096
                resp = self._gemini_client.models.generate_content(
                    model=model,
                    contents=clean_pmt,
                    config=t.GenerateContentConfig(
                        system_instruction=sys_inst,
                        temperature=0.3,
                        max_output_tokens=out_tokens,
                    ),
                )
                return resp.text.strip()
            except Exception as exc:
                err = str(exc)
                if "400" in err or "401" in err or "403" in err:
                    print(f"\n   ❌ [Gemini-{model}/{attempt}] {err[:80]}")
                    print(f"   ℹ️ Immediate failover to Groq ({cfg.GROQ_MODEL_FALLBACK})")
                    break
                wait = 5 if ("503" in err or "Unavailable" in err) else \
                       int(15 * (2 ** (attempt - 1))) if ("429" in err or "ResourceExhausted" in err) \
                       else 3
                print(f"\n   ⏳ [Gemini/{attempt}] {err[:40]}... {wait}s", end="", flush=True)
                for _ in range(wait):
                    time.sleep(1)
                    print(".", end="", flush=True)
                print(" ✓")
        print(f"\n   ⚠️  [{section}] Gemini failed → Groq fallback ({cfg.GROQ_MODEL_FALLBACK})")
        return self._groq_call(
            cfg.GROQ_MODEL_FALLBACK,
            _SECTION_INSTRUCTIONS[section],
            user_prompt,
        )

    # ── مُشغّل القسم (يعمل داخل ThreadPoolExecutor) ─────────────────────────
    def _run_section(
        self,
        section: str,
        office_data: OfficeData,
        plan_text: str,
    ) -> str:
        """يُشغّل نموذج القسم المُخصَّص ويُعيد النص الخام."""
        scfg     = self._SECTION_CFG[section]
        model    = getattr(cfg, scfg["model_attr"])
        prompt   = _build_section_prompt(section, office_data, plan_text)
        sys_inst = _SECTION_INSTRUCTIONS[section]

        # Gemini / Gemma4 — كلاهما عبر _gemini_call الموحَّد
        if scfg["provider"] in ("gemini", "gemini-gemma4"):
            return self._gemini_call(section, prompt)

        # Groq (summary + tasks) — مع Groq fallback عند الاستنفاد الكامل
        max_tok = 8192 if section == "summary" else 4096
        result  = self._groq_call(model, sys_inst, prompt, max_tokens=max_tok)
        if not result:
            print(f"\n   ⚠️  [{section}] Groq exhausted → Groq fallback ({cfg.GROQ_MODEL_FALLBACK})")
            if section == "tasks":
                # مهام: تعليمات JSON صريحة حتى لا يُنتج النص نثراً
                json_enforcement = (
                    "CRITICAL: RETURN ONLY RAW JSON ARRAY. "
                    "NO conversational text. NO markdown prose outside the JSON block. "
                    "Start your response with [ and end with ]. "
                    "The VERY LAST character of your response MUST be ] — "
                    "never stop generating before the JSON array is fully closed.\n\n"
                    + sys_inst
                )
                result = self._groq_call(
                    cfg.GROQ_MODEL_FALLBACK, json_enforcement, prompt, max_tokens=4096
                )
            else:
                result = self._groq_call(
                    cfg.GROQ_MODEL_FALLBACK, sys_inst, prompt, max_tokens=4096
                )

        # آخر خط دفاع: أي قسم فشل Groq فيه كلياً → Gemini بنفس تعليماته
        if not result and self._gemini_client:
            print(f"\n   🆘 [{section}] Groq completely exhausted → Gemini ({cfg.GEMINI_MODEL})")
            result = self._gemini_call(section, prompt)
        elif not result:
            print(f"\n   ❌ [{section}] Groq failed and Gemini unavailable — section empty.")
        return result

    # ── الواجهة الرئيسية ──────────────────────────────────────────────────────
    def analyze(
        self,
        office_data: OfficeData,
        plan_text: str = "",
        on_progress=None,
    ) -> dict[str, str]:
        """
        يُشغّل 4 خيوط متوازية ويُعيد:
          { 'summary': str, 'tasks': str, 'audit': str, 'challenges': str }
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        SECTIONS = ["summary", "tasks", "audit", "challenges"]
        results: dict[str, str] = {s: "" for s in SECTIONS}

        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="section") as pool:
            future_map = {
                pool.submit(self._run_section, s, office_data, plan_text): s
                for s in SECTIONS
            }
            for future in as_completed(future_map):
                section = future_map[future]
                try:
                    val = future.result() or ""
                    results[section] = val
                    if on_progress:
                        on_progress(section, bool(val.strip()))  # False if empty
                except Exception as exc:
                    print(f"\n   ❌ [{section}] Unexpected error: {exc}")
                    results[section] = ""
                    if on_progress:
                        on_progress(section, False)

        return results


# ─── Factories ────────────────────────────────────────────────────────────────
def get_orchestrator() -> ParallelOrchestrator:
    """يُعيد ParallelOrchestrator — المدخل المُوصَى به لـ main.py."""
    return ParallelOrchestrator()


if __name__ == "__main__":
    from data_parser import parse_row

    dummy_row = ["2025-01-01", "مكتب حلب", "سارة أحمد", "0912345678",
                 "http://plan.pdf"] + [""] * 112
    dummy_row[5]  = "خالد محمود"
    dummy_row[6]  = "0911111111"
    dummy_row[7]  = "تنظيم يوم ثقافي"
    dummy_row[8]  = "يوم ثقافي في الجامعة"
    dummy_row[9]  = "ثقافي"
    dummy_row[10] = "حضوري"
    dummy_row[11] = "مكتمل"
    dummy_row[115] = "ضعف التمويل"
    dummy_row[116] = "نأمل دعمًا لوجستيًا"

    data = parse_row(dummy_row)
    sample_plan = "الخطة الشهرية: 1. تنظيم يوم ثقافي 2. ورشة عمل تدريبية 3. اجتماع اللجنة"

    analyzer = get_analyzer()   # يختار تلقائيًا بناءً على LLM_PROVIDER في .env
    result = analyzer.analyze(data, sample_plan)
    print("\n" + "=" * 60)
    print(result)
