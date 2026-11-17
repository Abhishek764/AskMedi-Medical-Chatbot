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
folic acid; ferrous sulfate; vitamin d; zinc; oral rehydration salts;
glipizide; glyburide; pioglitazone; empagliflozin; dapagliflozin; linagliptin; liraglutide;
semaglutide; dulaglutide; insulin lispro; insulin aspart; insulin detemir; valsartan;
olmesartan; irbesartan; candesartan; ramipril; benazepril; captopril; carvedilol; bisoprolol;
propranolol; nebivolol; labetalol; diltiazem; verapamil; nifedipine; chlorthalidone;
spironolactone; torsemide; bumetanide; hydralazine; clonidine; isosorbide mononitrate;
nitroglycerin; digoxin; amiodarone; simvastatin; pravastatin; lovastatin; ezetimibe;
fenofibrate; rivaroxaban; dabigatran; heparin; enoxaparin; ticagrelor; prasugrel;
esomeprazole; lansoprazole; rabeprazole; sucralfate; misoprostol; metoclopramide;
prochlorperazine; promethazine; meclizine; bisacodyl; docusate; polyethylene glycol;
lactulose; senna; mesalamine; ursodiol; cephalexin; cefuroxime; ceftriaxone; cefdinir;
clindamycin; clarithromycin; erythromycin; levofloxacin; moxifloxacin; penicillin;
amoxicillin and clavulanate; sulfamethoxazole and trimethoprim; tetracycline; minocycline;
linezolid; vancomycin; rifampin; isoniazid; ethambutol; pyrazinamide; terbinafine;
clotrimazole; miconazole; nystatin; ketoconazole; itraconazole; valacyclovir; famciclovir;
tenofovir; emtricitabine; lamivudine; dolutegravir; efavirenz; ivermectin; albendazole;
mebendazole; permethrin; chloroquine; artemether and lumefantrine; primaquine;
diphenhydramine; hydroxyzine; levocetirizine; desloratadine; fluticasone; mometasone;
beclomethasone; ipratropium; tiotropium; formoterol; salmeterol; theophylline;
dextromethorphan; guaifenesin; pseudoephedrine; phenylephrine; benzonatate;
methylprednisolone; dexamethasone; hydrocortisone; triamcinolone; tramadol; codeine;
morphine; oxycodone; hydrocodone; buprenorphine; naloxone; naltrexone; methadone;
celecoxib; meloxicam; indomethacin; ketorolac; colchicine; allopurinol; febuxostat;
methotrexate; sulfasalazine; leflunomide; alendronate; risedronate; calcitriol;
calcium carbonate; magnesium oxide; potassium chloride; cyanocobalamin; thiamine;
bupropion; citalopram; paroxetine; venlafaxine; duloxetine; mirtazapine; trazodone;
nortriptyline; lithium; quetiapine; olanzapine; risperidone; aripiprazole; haloperidol;
lorazepam; diazepam; buspirone; zolpidem; melatonin; methylphenidate;
amphetamine; atomoxetine; donepezil; memantine; levodopa and carbidopa; pramipexole;
ropinirole; lamotrigine; topiramate; phenytoin; oxcarbazepine; pregabalin; sumatriptan;
rizatriptan; baclofen; cyclobenzaprine; tizanidine; tamsulosin; finasteride; dutasteride;
oxybutynin; tolterodine; sildenafil; tadalafil; estradiol; medroxyprogesterone;
norethindrone; levonorgestrel; progesterone; clomiphene; letrozole; tamoxifen; anastrozole;
testosterone; methimazole; propylthiouracil; liothyronine; acarbose; nicotine;
varenicline; disulfiram; acamprosate; hydroquinone; tretinoin; isotretinoin; benzoyl peroxide;
adapalene; mupirocin; silver sulfadiazine; lidocaine; timolol; latanoprost; brimonidine;
ofloxacin; tobramycin; artificial tears
"""

PAPER_TOPICS = """
asthma; type 2 diabetes; hypertension; dengue; tuberculosis; malaria; depression; anxiety;
migraine; chronic kidney disease; heart failure; atrial fibrillation; obesity; vitamin d;
covid-19; influenza vaccine; hpv vaccine; polycystic ovary syndrome; anemia; osteoarthritis;
rheumatoid arthritis; hepatitis b; fatty liver disease; gerd; irritable bowel syndrome;
insomnia; smoking cessation; stroke; epilepsy; dementia;
type 1 diabetes; gestational diabetes; coronary artery disease; hyperlipidemia; copd;
pneumonia; urinary tract infection; sepsis; typhoid; chikungunya; hiv; hepatitis c;
cirrhosis; peptic ulcer; inflammatory bowel disease; celiac disease; thyroid disease;
osteoporosis; gout; low back pain; parkinson disease; multiple sclerosis; schizophrenia;
bipolar disorder; adhd; autism; alcohol use disorder; breast cancer; cervical cancer;
colorectal cancer; lung cancer; prostate cancer; psoriasis; atopic dermatitis; acne;
glaucoma; cataract; otitis media; preeclampsia; menopause; endometriosis; childhood obesity;
malnutrition; iron deficiency; antimicrobial resistance; physical activity; sleep apnea
"""


def parse(block: str) -> list[str]:
    return [t.strip() for t in block.replace("\n", " ").split(";") if t.strip()]
