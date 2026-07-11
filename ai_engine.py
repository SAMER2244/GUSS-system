"""
ai_engine.py  —  V3.2 Strategic Auditor (Gemini-Only with Fallback & Retry)
=========================================================================
يُرسل بيانات المكتب + نص الخطة الشهرية إلى Gemini.

النموذج الافتراضي: Gemini 3.5 Flash (gemini-3.5-flash)
النموذج الاحتياطي (عند خطأ 429): Gemini 3.1 Flash Lite (gemini-3.1-flash-lite)
في حال تكرار خطأ 429: الانتظار والإعادة.
"""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod

import config as cfg
from data_parser import OfficeData, get_task_statistics
from logger import get_logger
from exceptions import AIAnalysisError

_log = get_logger("ai_engine")


# ─── System Instruction: Strategic Auditor Persona ───────────────────────────
_SYSTEM_INSTRUCTION = """
أنت مدقّق استراتيجي متخصص في تقييم الأداء المؤسسي للاتحاد العام لطلبة سوريا.
مهمتك: إعداد تقرير Audit مقارن احترافي شامل باللغة العربية الفصحى ذات الأسلوب الإداري الرسمي.

يجب أن يتضمن كل تقرير الأقسام التالية بالترتيب الآتي:

القسم الأول — الملخص التنفيذي الشامل
اكتب 3 إلى 5 جمل موجزة ومتماسكة، كل جملة مرتكزة على معطى محدد من البيانات (رقم أو اسم مهمة أو حالة تنفيذ)، تُغطي جميع المعطيات الآتية:
  - نظرة عامة على مستوى الأداء الكلي للمكتب خلال الشهر.
  - ملخص تحليلي لأبرز المهام المُنفَّذة والمنهجية المتبعة والقيمة المُضافة لكل منها.
  - التحديات العامة المُبلَّغ عنها وتأثيرها على مسار العمل.
  - الملاحظات الإضافية المُدرجة وما تنطوي عليه من توصيات أو رغبات.
قواعد الصياغة الإلزامية:
  - لا تربط أكثر من فكرة واحدة في الجملة الواحدة عبر «حيث» أو «مما» أو «بناءً على ذلك» — استخدم نقطة وابدأ جملة جديدة.
  - لا تكرر كلمة ربط واحدة أكثر من مرة في الفقرة كاملة.
يُحظر في هذا القسم استخدام أي أرقام تقييمية أو رموز تقنية أو بيانات وصفية خاما.
الأسلوب نثري رسمي حصرًا، مع الحرص على تصحيح أي أخطاء إملائية أو لغوية.

القسم الثاني — تقييم المهام المُنفَّذة
أنشئ في هذا القسم حصرًا كتلة JSON واحدة وفق الهيكل الآتي، دون أي نص خارجها:
```json
[
  {
    "task_id": "رقم المهمة",
    "original_name": "اسم المهمة كما وردَ في النموذج",
    "ai_insight": "2 إلى 3 جمل قصيرة مفصولة بنقاط. الجملة الأولى تصف الهدف والآلية. الجملة الثانية تذكر الأثر أو النتيجة. الجملة الثالثة (إن وجدت) تعالج الإشكاليات أو القيود."
  }
]
```
يُحظر تمامًا إدراج أي حقل تقييمي رقمي (impact_score أو ما شابهه) في المخرجات.
يجب تناول كل مهمة مذكورة في البيانات دون استثناء.

القسم الثالث — الاختناقات الإدارية والتحديات
صِف بأسلوب نثري رسمي الإشكاليات المذكورة في حقل إشكاليات كل مهمة، موحِّدًا المتشابه منها وصانِّفًا ما ينفرد بجدة، ومُصنِّفًا الأولوية (عالية / متوسطة / منخفضة) ضمن النص لا في بيانات منفصلة.
قيود الصياغة: لا تربط أكثر من فكرة في الجملة عبر «حيث» أو «مما». لا تكرر كلمة ربط أكثر من مرة في النص كاملاً.

القسم الرابع — تحليل المطابقة: الخطة المعتمدة مقابل الإنجاز الفعلي
حلّل بصورة مقارنة تفصيلية:
  أ) نسبة الالتزام بالخطة الشهرية المعتمدة.
  ب) الفجوات التنفيذية: ما خُطِّط له ولم يُنفَّذ.
  ج) الأعمال الاستثنائية: ما نُفِّذ خارج نطاق الخطة.
إذا كان نص الخطة غائبًا، أشر إلى ذلك صراحةً وأجرِ التحليل بناءً على بيانات النموذج وحدها.
قيود الصياغة: لا تربط أكثر من فكرة في الجملة عبر «حيث» أو «مما». لا تكرر كلمة ربط أكثر من مرة في النص كاملاً.

قواعد إلزامية مشتركة لجميع الأقسام:
أولًا: اللغة العربية الفصحى ذات الأسلوب الإداري الرسمي في جميع الأقسام النصية دون استثناء.
ثانيًا: يُحظر استخدام أي تنسيق Markdown (نجوم، ايموجي، شرائط، رموز) خارج كتلة JSON في القسم الثاني.
ثالثًا: العناوين تُكتب كنص عادي، مثال: «القسم الأول — الملخص التنفيذي الشامل».
رابعًا: لا يجوز إغفال أي معلومة واردة في البيانات المُدخَلة.
خامسًا: يُحظر تمامًا إدراج أي قيم رقمية تقييمية كالدرجات أو النقاط في أي قسم نصي."""


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
    max_chars = cfg.PLAN_TEXT_MAX_CHARS
    if plan_text and plan_text.strip():
        plan_section = (
            "=== نص الخطة الشهرية المعتمدة (مُستخرج من PDF) ===\n"
            f"{plan_text[:max_chars]}\n"
            + ("[... اقتُصر على الجزء الأول بسبب طول النص ...]\n"
               if len(plan_text) > max_chars else "")
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

    # ── بيانات المهام (نسخة نظيفة بدون الحقلين الختاميين) ────────────────────────
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


# ─── Per-Section System Instructions ─────────────────────────────────────────
_SECTION_INSTRUCTIONS: dict[str, str] = {

    "summary": """
You are a senior strategic auditor. Your sole task: write Section 1 — the Comprehensive Executive Summary.

Write 3-5 concise sentences, each grounded in a specific fact from the payload (a number, a task name, a status). Collectively cover all of the following:
  - An overview of the office's overall performance level for the month.
  - An analytical summary of key tasks: methodology and value delivered by each.
  - General challenges reported and their impact on work continuity.
  - Additional notes/observations and any embedded recommendations.

MANDATORY RULES:
  - IMPORTANT: You MUST generate the final analysis/response in ARABIC only. Use a professional, executive tone.
  - No English in the output.
  - No Markdown formatting (no asterisks, dashes, bullets) and no numerical scores.
  - Do NOT chain more than one subordinate clause per sentence using حيث/مما/بناءً على ذلك — use a period and start a new sentence instead.
  - Do NOT reuse the same connector word more than once in the whole paragraph.
  - No section headings — flowing prose sentences only.
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
    "ai_insight": "2-3 short sentences (periods allowed and encouraged). Do not fuse everything into one run-on clause chain."
  }
]
```

Quality criteria for each ai_insight:
  1. 2-3 short sentences (periods allowed and encouraged). Do not fuse everything into one run-on clause chain.
  2. Sentence 1: state the task objective and execution method.
  3. Sentence 2: describe the outcome or operational impact.
  4. Sentence 3 (optional): address constraints or issues if any exist in the data.
  5. Vary sentence openings: avoid starting consecutive insights with the same verb.
  6. Use management consulting vocabulary: operational efficiency, institutional readiness, structural capacity.
  7. No verbatim copying: transform raw field data into insight.

Example of the required quality:
  "نفّذ المكتب ورشة تدريبية حضورية حول حقوق الطلاب في قاعة المؤتمرات. أسهمت الورشة في رفع الوعي الحقوقي لدى المشاركين وتعزيز منظومة الدعم المؤسسي. أثّر التأخر في توفير المعدات التقنية على الجداول الزمنية المقررة."

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
  - Do NOT chain more than one idea per sentence using حيث/مما/بناءً على ذلك — use a period and start a new sentence instead.
  - Do NOT reuse the same connector word more than once in the entire response.
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
  - Do NOT chain more than one idea per sentence using حيث/مما/بناءً على ذلك — use a period and start a new sentence instead.
  - Do NOT reuse the same connector word more than once in the entire response.
""",
}


# ─── Per-Section Prompt Builder ───────────────────────────────────────────────
def _build_section_prompt(
    section: str,
    office_data: OfficeData,
    plan_text: str,
) -> str:
    """بيانات مُركَّزة لكل خيط — نفس البيانات، تعليمات الإخراج مختلفة."""
    stats = get_task_statistics(office_data)

    max_chars = cfg.PLAN_TEXT_MAX_CHARS
    plan_block = (
        f"=== نص الخطة الشهرية المعتمدة ===\n{plan_text[:max_chars]}\n"
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


# ─── Abstract Base ────────────────────────────────────────────────────────────
class _BaseAnalyzer(ABC):
    @abstractmethod
    def analyze(self, office_data: OfficeData, plan_text: str = "") -> str: ...


# ─── finish_reason inspector ─────────────────────────────────────────────────
def _check_finish_reason(response, section_name: str, model: str) -> None:
    """
    يفحص finish_reason للـ response ويسجّل تحذيراً صريحاً إذا كان MAX_TOKENS.
    يعمل مع كل من: response.candidates[0].finish_reason (Enum أو str).
    """
    try:
        candidate = response.candidates[0] if response.candidates else None
        if candidate is None:
            return
        reason = candidate.finish_reason
        # الـ SDK يُعيد Enum أو str حسب النسخة — نُحوِّله لـ str للمقارنة
        reason_str = reason.name if hasattr(reason, "name") else str(reason)
        if reason_str in ("MAX_TOKENS", "STOP_REASON_MAX_TOKENS", "2"):
            _log.warning(
                "⚠️  [Gemini/%s] Thread '%s' TRUNCATED — finish_reason=MAX_TOKENS. "
                "النص مقطوع في منتصفه. ارفع max_output_tokens في settings.yaml.",
                model, section_name
            )
        else:
            _log.debug(
                "   ✅ [Gemini/%s] Thread '%s' finish_reason=%s",
                model, section_name, reason_str
            )
    except Exception as e:
        _log.debug("   [finish_reason] Could not inspect reason: %s", e)


# ─── Gemini call helper with 429 fallback and retry logic ─────────────────────
def call_gemini_with_fallback(
    client,
    system_instruction: str,
    user_prompt: str,
    max_output_tokens: int = 4096,
    office_name: str = "غير محدد",
    section_name: str = "all"
) -> str:
    """
    يستدعي نموذج Gemini.
    النموذج الافتراضي: gemini-3.5-flash
    عند حدوث خطأ 429: يتم الانتقال إلى gemini-3.1-flash-lite
    عند حدوث خطأ 429 مجدداً على النموذج البديل: ينتظر 30 ثانية ويعيد المحاولة.
    """
    from google.genai import types as genai_types  # type: ignore

    def sanitize(text: str) -> str:
        import re
        text = text.encode("utf-8", errors="ignore").decode("utf-8")
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        text = re.sub(r"[\ud800-\udfff]", "", text)
        text = re.sub(r"[\ue000-\uf8ff]", "", text)
        return text

    sys_inst = sanitize(system_instruction)
    prompt = sanitize(user_prompt)

    # المحاولة الأولى باستخدام النموذج الافتراضي (Gemini 3.5 Flash)
    model = cfg.GEMINI_MODEL_DEFAULT
    try:
        _log.info("   🤖 [Gemini/%s] Calling for '%s' (Section: %s)...", model, office_name, section_name)
        config = genai_types.GenerateContentConfig(
            system_instruction=sys_inst,
            temperature=cfg.GEMINI_TEMPERATURE,
            max_output_tokens=max_output_tokens,
        )
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=config
        )
        text = response.text.strip()
        _check_finish_reason(response, section_name, model)
        return text
    except Exception as exc:
        err_msg = str(exc)
        is_temp_error = any(
            x in err_msg or x in err_msg.lower()
            for x in ["429", "503", "resourceexhausted", "rate", "unavailable", "demand",
                      "name resolution", "resolution", "dns", "connection", "timeout", "refused"]
        )
        if is_temp_error:
            # خطأ مؤقت -> الانتقال للنموذج البديل (Gemini 3.1 Flash Lite)
            _log.warning("   ⚠️  [Transient Error] Default model '%s' failed: %s. Switching to fallback '%s'...", model, err_msg[:100], cfg.GEMINI_MODEL_FALLBACK)
            model = cfg.GEMINI_MODEL_FALLBACK
            attempt = 0
            max_fallback_attempts = 3
            while attempt < max_fallback_attempts:
                attempt += 1
                try:
                    _log.info("   🤖 [Gemini/%s] Calling fallback model (Attempt %d/%d)...", model, attempt, max_fallback_attempts)
                    config = genai_types.GenerateContentConfig(
                        system_instruction=sys_inst,
                        temperature=cfg.GEMINI_TEMPERATURE,
                        max_output_tokens=max_output_tokens,
                    )
                    response = client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=config
                    )
                    text = response.text.strip()
                    _check_finish_reason(response, section_name, model)
                    return text
                except Exception as exc_fallback:
                    err_fallback = str(exc_fallback)
                    is_fallback_temp = any(
                        x in err_fallback or x in err_fallback.lower()
                        for x in ["429", "503", "resourceexhausted", "rate", "unavailable", "demand",
                                  "name resolution", "resolution", "dns", "connection", "timeout", "refused"]
                    )
                    if is_fallback_temp and attempt < max_fallback_attempts:
                        # خطأ مؤقت متكرر -> انتظر وأعد المحاولة
                        _log.warning("   ⏳ [Transient Error] Fallback '%s' also failed: %s (Attempt %d/%d). Waiting %ds...", model, err_fallback[:100], attempt, max_fallback_attempts, cfg.GEMINI_FALLBACK_WAIT)
                        time.sleep(cfg.GEMINI_FALLBACK_WAIT)
                    else:
                        _log.error("   ❌ [Gemini/%s] Fallback error after %d attempts: %s", model, attempt, err_fallback)
                        raise AIAnalysisError(str(err_fallback), section=section_name, model=model) from exc_fallback
        else:
            _log.error("   ❌ [Gemini/%s] Default model error: %s", model, err_msg)
            raise AIAnalysisError(str(exc), section=section_name, model=model) from exc


# ─── Gemini Analyzer (للتوافق القديم واختبارات debug_test.py) ──────────────────
class GeminiAnalyzer(_BaseAnalyzer):
    """
    محلل متوافق مع الواجهة القديمة ويستخدم منطق التبديل والانتظار الخاص بـ Gemini.
    """

    def __init__(self) -> None:
        if not cfg.GEMINI_API_KEY:
            raise AIAnalysisError(
                "❌ مفتاح Gemini API غير محدد. أضف GEMINI_API_KEY إلى ملف .env"
            )
        from google import genai                          # type: ignore
        self._client = genai.Client(api_key=cfg.GEMINI_API_KEY)
        _log.info("✅ Gemini engine initialized: Default=%s, Fallback=%s", cfg.GEMINI_MODEL_DEFAULT, cfg.GEMINI_MODEL_FALLBACK)

    def analyze(self, office_data: OfficeData, plan_text: str = "") -> str:
        prompt = _build_audit_prompt(office_data, plan_text)
        return call_gemini_with_fallback(
            self._client,
            _SYSTEM_INSTRUCTION,
            prompt,
            max_output_tokens=8192,
            office_name=office_data.get("office_name", "غير محدد"),
            section_name="all"
        )


# ─── Parallel Orchestrator ────────────────────────────────────────────────────
class ParallelOrchestrator:
    """
    يُشغّل 4 خيوط متوازية لكل مكتب، كل خيط يُنتج قسمًا واحدًا باستخدام Gemini مع Fallback & Retry.
    """

    def __init__(self) -> None:
        if not cfg.GEMINI_API_KEY:
            raise AIAnalysisError("❌ مفتاح Gemini API غير محدد. أضف GEMINI_API_KEY إلى .env")

        try:
            from google import genai  # type: ignore
            self._client = genai.Client(api_key=cfg.GEMINI_API_KEY)
        except ImportError:
            raise AIAnalysisError("❌ مكتبة google-genai غير مثبتة. شغّل: pip install google-genai")

        _log.info("✅ [Orchestrator] Ready — 4 threads using Gemini (Default: %s / Fallback: %s)", cfg.GEMINI_MODEL_DEFAULT, cfg.GEMINI_MODEL_FALLBACK)

    def _run_section(
        self,
        section: str,
        office_data: OfficeData,
        plan_text: str,
    ) -> str:
        prompt = _build_section_prompt(section, office_data, plan_text)
        sys_inst = _SECTION_INSTRUCTIONS[section]
        out_tokens = cfg.GEMINI_MAX_TOKENS_TASKS if section == "tasks" else cfg.GEMINI_MAX_TOKENS_DEFAULT
        
        try:
            return call_gemini_with_fallback(
                self._client,
                sys_inst,
                prompt,
                max_output_tokens=out_tokens,
                office_name=office_data.get("office_name", "غير محدد"),
                section_name=section
            )
        except Exception as e:
            _log.error("   ❌ [%s] Failed all attempts: %s", section, e)
            return ""

    def analyze(
        self,
        office_data: OfficeData,
        plan_text: str = "",
        on_progress=None,
    ) -> dict[str, str]:
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
                        on_progress(section, bool(val.strip()))
                except Exception as exc:
                    _log.error("   ❌ [%s] Unexpected orchestrator thread error: %s", section, exc)
                    results[section] = ""
                    if on_progress:
                        on_progress(section, False)

        return results


# ─── Factories ────────────────────────────────────────────────────────────────
def get_analyzer() -> _BaseAnalyzer:
    return GeminiAnalyzer()

def get_orchestrator() -> ParallelOrchestrator:
    return ParallelOrchestrator()


if __name__ == "__main__":
    data = {
        "office_name": "مكتب حلب",
        "submitter": "سارة أحمد",
        "submitter_phone": "0912345678",
        "target_month_name": "كانون الثاني",
        "target_month_num": 1,
        "monthly_plan_link": "http://plan.pdf",
        "general_challenges": "ضعف التمويل",
        "additional_notes": "نأمل دعمًا لوجستيًا",
        "tasks": [
            {
                "manager": "خالد محمود",
                "manager_phone": "0911111111",
                "name": "تنظيم يوم ثقافي",
                "description": "يوم ثقافي في الجامعة",
                "type": "ثقافي",
                "mechanism": "حضوري",
                "status": "مكتمل",
                "issues": "",
                "file_link": ""
            }
        ]
    }
    sample_plan = "الخطة الشهرية: 1. تنظيم يوم ثقافي 2. ورشة عمل تدريبية 3. اجتماع اللجنة"

    analyzer = get_analyzer()
    result = analyzer.analyze(data, sample_plan)
    print("\n" + "=" * 60)
    print(result)
