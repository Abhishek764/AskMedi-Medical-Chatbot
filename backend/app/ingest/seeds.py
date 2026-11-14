"""Seed lists for corpus v1. Common conditions (with India-relevant ones), widely used
generic medicines, and the topics we pull research reviews for. Grow these toward the
~1k-document target in .claude/idea.md §3; every addition is checked by the eval set."""

CONDITIONS = """
asthma; diabetes type 2; diabetes type 1; high blood pressure; heart attack; stroke;
heart failure; coronary artery disease; atrial fibrillation; high cholesterol; obesity;
dengue; malaria; tuberculosis; typhoid fever; cholera; chikungunya; covid-19; flu;
common cold; pneumonia; bronchitis; copd; sinusitis; strep throat; urinary tract infections;
kidney stones; chronic kidney disease; hepatitis b; hepatitis c; hepatitis a; fatty liver disease;
cirrhosis; gerd; peptic ulcer; irritable bowel syndrome; diarrhea; constipation; gallstones;
appendicitis; anemia; thalassemia; sickle cell disease; thyroid diseases; hypothyroidism;
hyperthyroidism; osteoporosis; osteoarthritis; rheumatoid arthritis; gout; back pain;
migraine; headache; epilepsy; dementia; alzheimer's disease; parkinson's disease;
depression; anxiety; bipolar disorder; schizophrenia; post-traumatic stress disorder;
insomnia; adhd; autism spectrum disorder; eczema; psoriasis; acne; fungal infections;
scabies; chickenpox; measles; mumps; hiv; sexually transmitted infections; polycystic ovary syndrome;
endometriosis; menopause; pregnancy; preeclampsia; infertility; breast cancer; cervical cancer;
lung cancer; colorectal cancer; prostate cancer; oral cancer; skin cancer; leukemia;
allergy; food allergy; anaphylaxis; snakebites; heat illness; dehydration; vitamin d deficiency;
vitamin b12 deficiency; iron deficiency; malnutrition; smoking; alcohol use disorder;
glaucoma; cataract; conjunctivitis; hearing loss; tooth decay; gum disease; rabies; leprosy
"""

MEDICINES = """
paracetamol; acetaminophen; ibuprofen; aspirin; diclofenac; naproxen; metformin; glimepiride;
sitagliptin; insulin glargine; amlodipine; losartan; telmisartan; enalapril; lisinopril;
metoprolol; atenolol; hydrochlorothiazide; furosemide; atorvastatin; rosuvastatin;
clopidogrel; warfarin; apixaban; levothyroxine; omeprazole; pantoprazole; ranitidine;
famotidine; ondansetron; domperidone; loperamide; amoxicillin; azithromycin; ciprofloxacin;
doxycycline; cefixime; metronidazole; nitrofurantoin; fluconazole; acyclovir; oseltamivir;
cetirizine; loratadine; fexofenadine; montelukast; salbutamol; albuterol; budesonide;
prednisolone; prednisone; sertraline; fluoxetine; escitalopram; amitriptyline; alprazolam;
clonazepam; gabapentin; levetiracetam; sodium valproate; carbamazepine; hydroxychloroquine;
folic acid; ferrous sulfate; vitamin d; zinc; oral rehydration salts
"""

PAPER_TOPICS = """
asthma; type 2 diabetes; hypertension; dengue; tuberculosis; malaria; depression; anxiety;
migraine; chronic kidney disease; heart failure; atrial fibrillation; obesity; vitamin d;
covid-19; influenza vaccine; hpv vaccine; polycystic ovary syndrome; anemia; osteoarthritis;
rheumatoid arthritis; hepatitis b; fatty liver disease; gerd; irritable bowel syndrome;
insomnia; smoking cessation; stroke; epilepsy; dementia
"""


def parse(block: str) -> list[str]:
    return [t.strip() for t in block.replace("\n", " ").split(";") if t.strip()]
