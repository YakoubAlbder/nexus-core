# Nexus Core

تطبيق شخصي (Habit & Analytics App) بيسجّل يوميتك (نص أو صوت)، يستخرج منها بيانات
منظمة عبر Gemini، يحفظها في Supabase، ويعرضها في Dashboard + مراجعة أسبوعية تفاعلية
مع الذكاء الاصطناعي.

## الفلسفة (مهم تقرأها قبل الكود)

النظام ده مش أداة تتبع جافة بتحطلك ✅/❌ على كل عادة. الافتراض الأساسي إنك إنسان
مش آلة: فيه أيام صعود وأيام هبوط، والتقدم مش خطي. لما تقصّر في حاجة، السؤال مش
"ليه فشلت؟" — السؤال "إيه السبب الحقيقي (نوم قليل، ضغط شغل، ضغط سكن...) اللي وراه؟".

عملياً ده انعكس في 3 حاجات في الكود:
1. **حقول بيانات تفهم لا تحاسب**: زي `fatigue_type` (تعب حقيقي ولا فتور مؤقت) و
   `sense_of_control_score` (شعورك بالتحكم في نفسك، مش بس مستوى الضغط عليك).
2. **برومبت الاستخراج** (`EXTRACTION_SYSTEM_PROMPT` في `lib/gemini_client.py`) بيوصّي
   Gemini صراحة إنه يوصف الموقف بحياد، مش يصيغه كتقصير.
3. **برومبت المراجعة الأسبوعية** (`WEEKLY_SYSTEM_PROMPT`) اتبنى بالكامل على إنه
   "مستشار متعاطف" مش "مراجع Performance" — بيربط التراجع بسببه الجذري بلطف، بيذكر
   إنجاز حقيقي كل أسبوع، ولما بيسأل عن خطة الأسبوع الجاي بيسأل كدعوة للتفكير مش
   كمطلب صارم.

لو حبيت تغيّر النبرة أكتر أو أقل مستقبلاً، الملفين دول (`lib/gemini_client.py` لنبرة
الذكاء الاصطناعي، و`app.py`/`pages/1_Dashboard.py` لنصوص الواجهة) هما المكان الوحيد
اللي محتاج تعدّله.

## لماذا هذا الـ Stack

| الطبقة | الاختيار | السبب |
|---|---|---|
| الواجهة والباك إند | **Streamlit** | ملف Python واحد لكل صفحة، بدون فرونت إند منفصل، ونشر مجاني على Streamlit Community Cloud |
| القاعدة | **Supabase (Postgres, free tier)** | سحابية → تقدر تدخل من اللابتوب أو التليفون من أي مكان، وده كان شرطك إنك توصله من غير ما اللابتوب يفضل شغال |
| الـ LLM | **Gemini API** | free tier سخي فعلاً مقارنة بـ Claude API اللي مفهوش free tier دائم — مناسب لمشروع شخصي هدفه 0$ |
| الرسوم البيانية | **Plotly** | تفاعلية (hover/zoom) وبتشتغل جوه Streamlit من غير إعداد إضافي |

**التكلفة المتوقعة: 0$** طالما فضلت جوه حدود الـ free tier بتاع كل خدمة (Supabase
free tier وGemini free tier وStreamlit Community Cloud). لاحظ إن Google بتقدر
تستخدم بيانات الـ free tier لتحسين النماذج (راجع سياسة الخصوصية بتاعتهم) — لو
اليوميات عندك فيها حاجة حساسة جداً فكّر في الترقية للـ paid tier بتاع Gemini اللي
معاه ضمان أقوى للخصوصية.

## هيكل المشروع

```
nexus_core/
├── app.py                      # صفحة الدخول اليومي (نص/صوت → استخراج → مراجعة → حفظ)
├── pages/
│   ├── 1_Dashboard.py          # الرسوم البيانية والارتباطات
│   └── 2_Weekly_Review.py      # المقابلة الأسبوعية الآلية (AI Interviewer)
├── lib/
│   ├── schemas.py              # Pydantic models = شكل البيانات المستخرجة
│   ├── gemini_client.py        # كل نداءات Gemini (استخراج + المحلل الأسبوعي)
│   ├── db.py                   # كل التعامل مع Supabase
│   ├── analysis.py             # حساب الإحصائيات الأسبوعية والارتباطات
│   └── auth.py                 # بوابة كلمة مرور بسيطة
├── schema.sql                  # DDL بتاع Supabase — يتشغل مرة واحدة بس
├── requirements.txt
└── .streamlit/secrets.toml.example
```

## خطوات الإعداد (من الصفر)

### 1. Supabase (القاعدة)
1. اعمل حساب مجاني على [supabase.com](https://supabase.com) وأنشئ Project جديد.
2. من *SQL Editor* داخل المشروع، افتح ملف `schema.sql` من هنا وشغّله كامل (New query → Paste → Run). ده هيعمل كل الجداول.
3. من *Project Settings → API* خد `Project URL` و `anon public key` — دول هتحتاجهم في الـ secrets.

### 2. Gemini API (المحرك الذكي)
1. روح [aistudio.google.com](https://aistudio.google.com) وسجّل دخول بحساب Google، واعمل API Key من *Get API Key*.
2. راجع [صفحة الأسعار](https://ai.google.dev/gemini-api/docs/pricing) وشوف إيه النموذج المتاح مجاناً دلوقتي (الكود مضبوط افتراضياً على `gemini-3.5-flash` — لو الاسم اتغير، غيّره في `secrets.toml` بس، مش في الكود).

### 3. تشغيل محلي (اختياري، لو عايز تجرب قبل النشر)
```bash
cd nexus_core
python -m venv venv && source venv/bin/activate   # أو venv\Scripts\activate على ويندوز
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# افتح secrets.toml واملأ APP_PASSWORD وGEMINI_API_KEY وبيانات Supabase
streamlit run app.py
```

### 4. النشر على Streamlit Community Cloud (مجاني، ويشتغل من التليفون من أي مكان)
1. ارفع المجلد ده على GitHub repo جديد (خاص أفضل — الملف فيه بيانات شخصية).
   ```bash
   git init && git add . && git commit -m "Nexus Core v1"
   git branch -M main
   git remote add origin https://github.com/<username>/nexus-core.git
   git push -u origin main
   ```
   (`.gitignore` هنا بيمنع رفع `secrets.toml` بالغلط.)
2. روح [share.streamlit.io](https://share.streamlit.io)، سجّل دخول بحساب GitHub، واختار *New app* → اختار الـ repo → main file: `app.py`.
3. قبل ما تعمل Deploy، افتح *Advanced settings → Secrets* والصق فيها نفس محتوى `secrets.toml.example` بس بالقيم الحقيقية بتاعتك.
4. Deploy. هتاخد رابط زي `https://your-app.streamlit.app` — افتحه من موبايلك وضيفه كـ Shortcut على الشاشة الرئيسية عشان يحس إنه App حقيقي.

### 5. الاستخدام اليومي
- افتح الرابط من اللابتوب أو الموبايل → ادخل كلمة المرور.
- فضفض نصاً أو صوتاً (المتصفح هيطلب إذن الميكروفون أول مرة).
- راجع اللي Gemini استخرجه وعدّله لو غلط في حاجة، واحفظ.
- في آخر الأسبوع افتح "المراجعة الأسبوعية" وابدأ المقابلة.

## ملاحظات هندسية مهمة

- **الـ Gemini SDK بيتغير بسرعة.** كل نداءات الـ API متجمعة في `lib/gemini_client.py`
  بس، فلو Google غيّرت اسم الميثود أو الشكل تاني، التعديل هيبقى في مكان واحد.
- **حفظ البيانات بيتم بـ upsert يومي**، يعني لو رجعت عدّلت يومية نفس اليوم مرتين
  هتتحدث مش تتكرر.
- **الأمان**: البوابة في `lib/auth.py` كلمة مرور بسيطة بس — كافية لمنع أي حد يوصل
  للرابط بالصدفة، مش حماية بنكية. متشاركش الرابط مع حد.
- **الميكروفون على الموبايل**: `st.audio_input` بيحتاج HTTPS (Streamlit Cloud
  بيوفره تلقائي) ومتصفح بيدعم الميزة — Chrome/Safari الحديثين تمام.

## خطوات تالية مقترحة (v2)
- Cron مجاني (GitHub Actions مثلاً) يفتح المراجعة الأسبوعية تلقائي كل يوم جمعة بدل ما تفتحها يدوي.
- Export أسبوعي كـ PDF/تقرير من نفس بيانات `weekly_reports`.
- ربط أذكار الصباح/المساء بـ push notification (يحتاج بنية إضافية خارج Streamlit).
