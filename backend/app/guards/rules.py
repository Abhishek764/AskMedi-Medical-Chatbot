"""Rule lists for the input guard.

Rules favour recall for crisis and emergency (a false alarm shows a helpline card; a miss
can cost a life). Every list has eval rows in tests/test_guards.py. A trained classifier
can be added beside these later; rules stay as the floor, and either one firing triggers.
"""

from __future__ import annotations

from app.guards.text import compile_all

_I = r"(?:\bi\b|\bi'm\b|\bim\b|\bme\b|\bmy\b|\bmyself\b|\bmain\b|\bmujhe\b|\bmera\b|\bmeri\b)"

# Someone at risk now (first person, intent, plans, hopelessness).
CRISIS_FIRST_PERSON = compile_all(
    [
        r"\b(kill|hurt|harm|cut|hang|shoot|poison|drown)(ing)? (my ?self|myself)\b",
        r"\b(end|take) (my|it) (own )?(life|all)\b",
        r"\bend it all\b",
        r"\b(want|wanna|going|plan|planning|ready|decided) to (die|end it|end my life|kill myself)\b",
        r"\b(i|i'm|im) (want to|wanna|going to|gonna) (die|disappear forever)\b",
        r"\bsuicid(e|al)\b.*\b(i|i'm|im|me|my|myself)\b",
        r"\b(i|i'm|im|me|my|myself)\b.*\bsuicid(e|al)\b",
        r"\b(no|not any) (reason|point) (to|in) (live|living|go on|going on)\b",
        r"\b(better off|everyone would be better) (dead|without me)\b",
        r"\bdon'?t want to (live|be alive|wake up|exist)\b",
        r"\bcan'?t (go on|take it anymore|do this anymore)\b",
        r"\b(self ?harm|self harming|cutting myself)\b",
        r"\bwrote (a|my) (suicide )?note\b",
        r"\bsaying goodbye (to everyone|forever)\b",
        # Hinglish
        r"\b(marna|mar jana|mar jaun|mar jaunga|mar jaungi|khudkushi|aatmahatya)\b",
        r"\bjeena nahi (chahta|chahti)\b",
        r"\bzindagi (khatam|khtm)\b",
    ]
)

# Asking for means or lethality: always crisis, whoever it is "for".
CRISIS_METHOD = compile_all(
    [
        r"\b(lethal|fatal|deadly|overdose) (dose|amount|quantity)\b",
        r"\bhow (many|much) .{0,40}\b(to|would) (die|kill|be fatal|be lethal|overdose)\b",
        r"\b(painless|quick|easy|quickest|easiest|best|surest) way to (die|kill (my ?self|myself|yourself|someone)|end (it|my life))\b",
        r"\bhow (to|do i|can i|do you) (kill|hang|poison) (my ?self|yourself|oneself)\b",
        r"\bhow to (commit )?suicide\b",
        r"\b(method|methods|ways) (of|for|to) (suicide|killing (my ?self|yourself))\b",
        r"\bwhich (pills|medicine|medication|drugs?) .{0,30}\b(die|kill|end)\b",
    ]
)

# Talking about the topic without first-person risk: answer, but attach helplines.
CRISIS_TOPIC = compile_all([r"\bsuicid", r"\bself ?harm", r"\bkill (my|him|her|them)sel(f|ves)\b"])

# Fiction / hypothetical framing used to get around safety rules.
FICTION_FRAMING = compile_all(
    [
        r"\b(for|in) (a|my) (story|novel|book|script|screenplay|game|poem|roleplay|role play)\b",
        r"\b(hypothetically|in theory|asking for a friend|pretend|imagine)\b",
        r"\bmy character\b",
    ]
)

# Acute medical emergency happening now.
EMERGENCY = compile_all(
    [
        rf"{_I}.{{0,40}}\b(chest (pain|pressure|tightness)|crushing pain)\b",
        r"\b(chest (pain|pressure|tightness)|crushing pain)\b.{0,40}\b(now|right now|spreading|arm|jaw|sweating)\b",
        r"\b(can'?t|cannot|unable to|struggling to|hard to) breathe?\b",
        r"\b(face (is )?(drooping|droops)|slurred speech|sudden (numbness|weakness)|one side of (my|his|her) (face|body))\b",
        r"\b(overdosed|took too many|swallowed (a|the|some)?.{0,25}(pills|tablets|bleach|poison|battery|chemical))\b",
        r"\b(unconscious|not breathing|unresponsive|passed out and)\b",
        r"\b(bleeding (heavily|a lot|won'?t stop|wont stop)|severe bleeding|lots of blood)\b",
        r"\b(throat|tongue|lips?) (is |are )?(swelling|closing|swollen)\b",
        r"\banaphyla",
        r"\b(having|had) a (seizure|stroke|heart attack)\b",
        r"\b(seizure|fitting|convulsing) (now|right now|won'?t stop)\b",
        r"\b(baby|child|infant|toddler) .{0,30}\b(not breathing|blue|unresponsive|choking|swallowed)\b",
        r"\bchoking\b",
        r"\bsnake ?bite|bitten by a snake\b",
        r"\bpoisoned\b",
    ]
)

EMERGENCY_TOPIC = compile_all(
    [r"\b(heart attack|stroke|anaphylaxis|overdose|seizure|cardiac arrest|sepsis)\b"]
)

# Prompt injection / jailbreak / system prompt extraction.
INJECTION = compile_all(
    [
        r"\b(ignore|disregard|forget|override) (all |any |the |your )?(previous|prior|above|earlier|system) (instructions|prompts?|rules|messages)\b",
        r"\b(ignore|bypass|disable) (your |the )?(rules|guidelines|safety|filters|guardrails|restrictions)\b",
        r"\b(reveal|show|print|repeat|output|leak|tell me) (me )?(your |the )?(system prompt|instructions|hidden prompt|initial prompt|developer message)\b",
        r"\bwhat (is|are) your (system prompt|instructions)\b",
        r"\b(dan|developer mode|jailbreak|jailbroken|do anything now)\b",
        r"\byou are (now )?(no longer|not) (bound|restricted|askmedi)\b",
        r"<\s*/?\s*(system|assistant|instructions?)\s*>",
        r"\b(new|updated) (system )?instructions?:",
    ]
)

# Persona requests (companion/therapist/doctor role-play).
PERSONA = compile_all(
    [
        r"\b(act|pretend|behave|roleplay|role play) (as|like|to be) (my |a |an )?(therapist|psychologist|counsell?or|doctor|physician|girlfriend|boyfriend|friend|partner|psychiatrist|nurse)\b",
        r"\bbe my (therapist|psychologist|counsell?or|doctor|girlfriend|boyfriend|best friend|partner)\b",
        r"\byou are (my|now my) (therapist|doctor|girlfriend|boyfriend|friend)\b",
    ]
)

# Ingesting non-food chemicals, risky substitutions, stopping prescribed medicine.
HARMFUL_SUBSTANCE = compile_all(
    [
        r"\b(replace|substitute|swap|instead of)\b.{0,40}\b(salt|sugar|food|water)\b.{0,40}\b(bromide|chloride of|borax|bleach|chemical)\b",
        r"\b(bromide|borax|bleach|chlorine dioxide|mms|miracle mineral|hydrogen peroxide|turpentine|kerosene|methanol|antifreeze)\b.{0,40}\b(drink|eat|take|swallow|ingest|consume|instead|substitute|replace|cure|dose)\b",
        r"\b(drink|eat|take|swallow|ingest|consume|cure)\b.{0,40}\b(bromide|borax|bleach|chlorine dioxide|mms|miracle mineral|turpentine|kerosene|methanol|antifreeze)\b",
        r"\b(stop|quit|come off) (taking )?(my )?(insulin|blood thinners?|warfarin|antidepressants?|seizure med(ication)?s?|chemo(therapy)?|medications?|medicines?|tablets)\b",
        r"\b(how to|can i) (make|cook|extract)\b.{0,30}\b(drugs?|opioids?|meth|lsd)\b",
    ]
)

# Personal dosing (refused for public users; label-cited for providers).
DOSING = compile_all(
    [
        r"\bhow (much|many) .{0,40}\b(should|can|do) (i|my|he|she|we|they|you)\b.{0,20}\b(take|give|use|have)\b",
        r"\b(dose|dosage|dosing) (of|for)\b",
        r"\b(what|which) (dose|dosage)\b",
        r"\bhow often (should|can|do) (i|my|he|she|we) (take|give)\b",
        r"\b\d+(\.\d+)? ?(mg|mcg|ml|g|iu|units?)\b.{0,30}\b(ok|okay|safe|enough|too much)\b",
        r"\bmaximum (dose|daily dose|amount)\b",
        r"\bcan i (take|give)\b.{0,40}\b(with|and|together)\b",  # interaction for self
    ]
)

# Asking for a personal diagnosis.
DIAGNOSIS = compile_all(
    [
        r"\bdo i have\b",
        r"\b(diagnose|diagnosis for) (me|my|this)\b",
        r"\bwhat('s| is) wrong with (me|my)\b",
        r"\b(is it|could it be|am i having)\b.{0,30}\b(cancer|diabetes|tumou?r|covid|hiv|stroke|infection)\b",
        r"\bwhat (disease|condition|illness) do i\b",
        r"\b(read|interpret) my (report|results|blood test|scan|x ?ray|mri|ecg|lab)\b",
    ]
)

# Signals the message is about health or medicine.
MEDICAL_TERMS = compile_all(
    [
        r"\b(pain|ache|aches|fever|cough|cold|flu|rash|itch|swelling|nausea|vomit\w*|diarrh\w*|constipat\w*|dizz\w*|fatigue|tired\w*|headache|migraine|bleed\w*|infection|inflam\w*|allerg\w*|symptom\w*|sore|cramp\w*|insomnia|sleep|stress|anxi\w*|depress\w*|mental|panic|suicid\w*|self ?harm|grief|trauma|ptsd|bipolar|schizo\w*|addict\w*|alcohol\w*|smok\w*|sneez\w*|breath\w*|wheez\w*|lump|wound|burn|bruise)\b",
        r"\b(disease|disorder|syndrome|condition|cancer|tumou?r|diabet\w*|asthma|hypertension|blood pressure|cholesterol|thyroid|arthritis|covid|hiv|aids|malaria|dengue|typhoid|tuberculosis|tb|hepatitis|anemia|anaemia|obesity|stroke|heart|kidney|liver|lung|stomach|skin|brain|bone|blood|eye|ear|teeth|tooth|gum|pregnan\w*|period|menstrua\w*|fertility|vaccin\w*|immun\w*|virus|bacteria\w*|fung\w*|parasit\w*|ulcer|gastritis|acid\w*|reflux|epilep\w*|seizure|dementia|alzheimer\w*|parkinson\w*|autism|adhd|eczema|psoriasis|acne)\b",
        r"\b(medicine|medication|medic\w*|drug|drugs|tablet|tablets|pill|pills|capsule|syrup|injection|vaccine|antibiotic\w*|antiviral|painkiller|insulin|steroid\w*|dose|dosage|prescription|side effects?|pharmac\w*|doctor|clinic|hospital|nurse|surgery|treatment|therapy|diagnos\w*|health|healthy|diet|nutrition|vitamin\w*|supplement\w*|exercise|calorie\w*|bmi|weight)\b",
        r"\b\w+(mab|pril|olol|sartan|statin|cillin|mycin|cycline|floxacin|azole|prazole|tidine|pine|done|pam|lam|vir|parin|gliptin|formin|profen)\b",
        r"\b(paracetamol|acetaminophen|ibuprofen|aspirin|metformin|amoxicillin|cetirizine|omeprazole|dolo|crocin|azithromycin|atorvastatin|amlodipine|losartan|levothyroxine|salbutamol|albuterol|prednisolone|ors)\b",
    ]
)

# Clearly not medical: code, homework, trivia, creative writing.
OFF_TOPIC = compile_all(
    [
        r"\b(python|javascript|java|c\+\+|sql|html|css|code|coding|program|function|algorithm|debug|compile)\b",
        r"\b(essay|homework|poem|lyrics|story|joke|recipe|movie|song|cricket|football|stock|crypto|bitcoin|weather|capital of|president|election|translate)\b",
    ]
)

GREETING = compile_all(
    [
        r"^(hi|hello|hey|hii+|namaste|good (morning|afternoon|evening)|thanks|thank you|ok|okay)( there| askmedi)?$"
    ]
)
