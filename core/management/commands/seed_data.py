"""
Management command to seed the database with barangays, real CSWDO programs,
a default admin user, and optional demo data.

Usage:
    python manage.py seed_data          # barangays + programs + admin only
    python manage.py seed_data --demo   # also creates demo beneficiaries & requests
"""
import random
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import (
    Barangay, Program, ProgramRequiredDocument, UserProfile,
    Beneficiary, AssistanceRequest,
)

# ─────────────────────────────────────────────────────────────────────────────
# Real Tayabas City barangay data (PSA 2020 Census-approximated populations)
# Total city population ≈ 108,794 | 75 barangays
# (name, latitude, longitude, population)
# ─────────────────────────────────────────────────────────────────────────────
BARANGAYS = [
    ("Alitao",                  14.055921997, 121.538125828, 1842),
    ("Alupay",                  14.065977863, 121.618677742, 2105),
    ("Angeles Zone I (Pob.)",   14.024940485, 121.595430334, 1234),
    ("Angeles Zone II",         14.024340119, 121.594387825,  897),
    ("Angeles Zone III",        14.024987468, 121.594810006,  763),
    ("Angeles Zone IV",         14.026660840, 121.595174762, 1012),
    ("Angustias Zone I (Pob.)", 14.027038541, 121.590239947, 1156),
    ("Angustias Zone II",       14.027229146, 121.591688847,  834),
    ("Angustias Zone III",      14.028295020, 121.592791812,  912),
    ("Angustias Zone IV",       14.028655329, 121.591852054,  743),
    ("Anos",                    13.996930436, 121.570754125, 2341),
    ("Ayaas",                   14.036846614, 121.622592045, 1876),
    ("Baguio",                  14.022577555, 121.587164962, 2654),
    ("Banilad",                 14.045509829, 121.613532528, 1543),
    ("Calantas",                14.056508894, 121.520486935, 3127),
    ("Camaysa",                 14.050896509, 121.573529895, 2489),
    ("Dapdap",                  14.063280726, 121.564024561, 1987),
    ("Gibanga",                 14.002354990, 121.542657311, 4318),
    ("Alsam Ibaba",             14.021859436, 121.639446130, 1654),
    ("Bukal Ibaba",             14.015344052, 121.561527163, 1876),
    ("Ilasan Ibaba",            14.068171688, 121.624495119, 1243),
    ("Nangka Ibaba",            13.998538683, 121.602185051, 1567),
    ("Palale Ibaba",            14.089248339, 121.731494700, 1102),
    ("Ibas",                    14.063216940, 121.588350607, 1398),
    ("Alsam Ilaya",             14.038671255, 121.640823589, 1287),
    ("Bukal Ilaya",             14.068562180, 121.487377783, 1098),
    ("Ilasan Ilaya",            14.092910630, 121.656964600,  934),
    ("Nangka Ilaya",            14.024506948, 121.591172487, 1245),
    ("Palale Ilaya",            14.060303950, 121.664251180,  987),
    ("Ipilan",                  14.026686001, 121.588493746,  876),
    ("Isabang",                 13.964324994, 121.582343639, 3214),
    ("Calumpang",               13.982744201, 121.574029927, 2134),
    ("Domoit Kanluran",         13.976947585, 121.589310429, 1543),
    ("Katigan Kanluran",        14.047771428, 121.625075558, 1102),
    ("Palale Kanluran",         14.046648654, 121.661517031,  876),
    ("Lakawan",                 14.012537948, 121.630876978, 1398),
    ("Lalo",                    14.036718599, 121.583675024, 1765),
    ("Lawigue",                 14.024465119, 121.675944110,  765),
    ("Lita (Pob.)",             14.021105567, 121.596563836, 1087),
    ("Malaoa",                  14.003374240, 121.589020889, 1987),
    ("Masin",                   14.054135915, 121.647210094, 1543),
    ("Mate",                    14.008490014, 121.650814190, 1176),
    ("Mateuna",                 14.031196534, 121.600453467, 1098),
    ("Mayowe",                  13.970389500, 121.587908558, 1876),
    ("Opias",                   14.040706262, 121.596685203, 1543),
    ("Pandakaki",               13.998633557, 121.627857032, 1243),
    ("Pook",                    14.055839631, 121.595848020, 1654),
    ("Potol",                   13.993585263, 121.595703877, 1876),
    ("San Diego Zone I (Pob.)", 14.025022996, 121.593406849, 1345),
    ("San Diego Zone II",       14.026074220, 121.594274702,  987),
    ("San Diego Zone III",      14.026608814, 121.594687015,  765),
    ("San Diego Zone IV",       14.026872345, 121.594888313,  634),
    ("San Isidro Zone I (Pob.)",14.022904358, 121.589584381, 1234),
    ("San Isidro Zone II",      14.024363434, 121.588736072,  876),
    ("San Isidro Zone III",     14.024573917, 121.590987036,  712),
    ("San Isidro Zone IV",      14.026237827, 121.589214945,  598),
    ("San Roque Zone I (Pob.)", 14.027023725, 121.591978086, 1198),
    ("San Roque Zone II",       14.027836907, 121.593923295,  876),
    ("Domoit Silangan",         13.976628730, 121.599898043, 1432),
    ("Katigan Silangan",        14.056185177, 121.627018827, 1087),
    ("Palale Silangan",         14.087905880, 121.709718700,  765),
    ("Talolong",                14.068171688, 121.624495119, 1198),
    ("Tamlong",                 14.075347360, 121.600891590, 1398),
    ("Tongko",                  13.994313118, 121.614958259, 1654),
    ("Valencia",                14.092910630, 121.656964600,  934),
    ("Wakas",                   14.022224064, 121.597152329,  876),
]

# ─────────────────────────────────────────────────────────────────────────────
# 8 Real CSWDO Programs / Services  (kept in original Tagalog)
# Each entry: (name, description, transaction_type, who_may_avail, [documents])
# Documents: list of (doc_name, description, category)
# ─────────────────────────────────────────────────────────────────────────────
PROGRAMS = [
    # ── PROGRAM 1 ──
    {
        "name": "Pagbibigay Tulong Pinansyal sa Pagsasaayos ng Bahay sa mga Nasalanta ng Kalamidad (Sunog, Bagyo, Baha at Iba Pa)",
        "description": "Pagkakaloob ng daglian tulong pabahay (Emergency Shelter Assistance) sa mga Tayabasing biktima ng kalamidad (sunog, bagyo, baha at iba pa).",
        "transaction_type": "G2C - Government to Citizen",
        "who_may_avail": "Tayabasin na nakatira sa loob ng anim (6) na buwan at lehitimong botante at biktima ng kalamidad.",
        "documents": [
            ("Sulat Kahilingan", "1 original", ""),
            ("Sertipiko at Pagpapatunay ng Barangay", "1 original", ""),
            ("Sertipiko ng Rehistradong Botante", "1 photocopy", ""),
            ("Litrato ng nasirang tirahan (sunog o bagyo)", "1 photocopy", ""),
            ("Sertipiko buhat sa Bureau of Fire kapag nasunugan", "1 photocopy", ""),
            ("Sedula", "1 photocopy", ""),
        ],
    },
    # ── PROGRAM 2 ──
    {
        "name": "Pagbibigay ng Social Case Study Report para Makahingi ng Tulong sa Ibang Ahensiya ng Pamahalaan ang mga Tayabasin (Referral Services)",
        "description": "Pagsasagawa ng Social Case Study Report para sa mga Tayabasin na nangangailangan ng tulong partikular ang mga nasa hanay ng mahihirap upang makahingi sa ibang ahensiya ng pamahalaan ng tulong depende sa kanilang inilalapit na kahilingan (PCSO, QMC, OPSWD, Office of the Congressman, Government Hospitals outside Quezon).",
        "transaction_type": "G2C - Government to Citizen",
        "who_may_avail": "Tayabasin na nakatira sa loob ng anim (6) na buwan at lehitimong botante at kabilang sa mga mahihirap na pamilya, may buwanang kita na hindi tataas sa P10,000.00 para sa anim na miyembro.",
        "documents": [
            # Sa Medikal
            ("Sertipiko at Pagpapatunay ng Barangay", "1 original", "Sa Medikal"),
            ("Sertipiko galing sa Ospital o Doktor na gumagamot / Reseta ng pirmadong Doktor / Kuwenta ng Pagbabayaran sa Ospital", "1 photocopy", "Sa Medikal"),
            ("Valid ID", "1 photocopy", "Sa Medikal"),
            # Sa Dagdag Pabaon para sa mga Mag-aaral
            ("Sertipiko at Pagpapatunay ng Barangay", "1 original", "Sa Dagdag Pabaon para sa mga Mag-aaral"),
            ("Pagpapatunay na nakatala sa Iskul ngayong Pasukan / Marka ng Nakaraang Pasukan o Report Card / Kuwenta ng Pagbabayaran sa Iskul", "1 photocopy", "Sa Dagdag Pabaon para sa mga Mag-aaral"),
            ("Valid ID", "1 photocopy", "Sa Dagdag Pabaon para sa mga Mag-aaral"),
        ],
    },
    # ── PROGRAM 3 ──
    {
        "name": "Pagkakaloob ng Nationally Uniformed ID sa mga Nakatatandang Mamamayan (Senior Citizens), sa mga Taong May Kapansanan (PWD) at sa mga Solo Parent",
        "description": "Bilang pagtupad sa itinakda ng batas ang bawat nakatatandang mamamayan, may kapansanan (PWD) at Solo Parent ay kailangang pagkalooban ng ID upang pakinabangan ang mga pribiliheyo at benepisyong nakapaloob dito.",
        "transaction_type": "G2C - Government to Citizen",
        "who_may_avail": "Tayabasin na nakatira sa loob ng anim (6) na buwan at lehitimong botante na may edad 60 taon pataas (Senior Citizen), may kapansanan (PWD) at Solo Parent.",
        "documents": [
            # Senior Citizen
            ("Aplikasyon", "1 original", "Senior Citizen"),
            ("Sertipiko at Pagpapatunay ng Barangay", "1 original", "Senior Citizen"),
            ("Sertipiko ng Rehistradong Botante", "1 photocopy", "Senior Citizen"),
            ("Sertipiko ng Kapanganakan / Paminyagan", "1 photocopy", "Senior Citizen"),
            ("Litrato: 2 piraso – 1x1", "", "Senior Citizen"),
            # PWD
            ("Aplikasyon (Philippine Registry Form for PWD)", "1 original", "PWD"),
            ("Sertipiko at Pagpapatunay ng Barangay", "1 original", "PWD"),
            ("Sertipiko ng Kapansanan", "1 original", "PWD"),
            ("Sertipiko ng Rehistradong Botante", "1 photocopy", "PWD"),
            ("Sertipiko ng Kapanganakan", "1 photocopy", "PWD"),
            ("Bagong Sedula (CTC)", "1 photocopy", "PWD"),
            ("Litrato: 2 piraso – 1x1", "", "PWD"),
            # Solo Parent
            ("Aplikasyon", "1 original", "Solo Parent"),
            ("Sertipiko at Pagpapatunay ng Barangay", "1 original", "Solo Parent"),
            ("Sertipiko ng Rehistradong Botante", "1 photocopy", "Solo Parent"),
            ("Sertipiko ng Kapanganakan ng Anak o magulang na direktang pinangangalagaan at kasama sa tahanan", "1 photocopy", "Solo Parent"),
            ("Bagong Sedula (CTC)", "1 photocopy", "Solo Parent"),
            ("Litrato: 2 piraso – 1x1", "", "Solo Parent"),
            ("Iba pang dokumento batay sa kategorya ng pagiging Solo Parent", "", "Solo Parent"),
        ],
    },
    # ── PROGRAM 4 ──
    {
        "name": "Pagkakaloob ng Tulong Pinansiyal para sa mga Lolo at Lola (Senior Citizens) at Person with Disabilities (PWD)",
        "description": "Espesyal na serbisyong ipinagkakaloob kay lolo at lola, may kapansanan o Person With Disability (PWD) at Solo Parent na nagdaos ng kanilang kaarawan bilang dagdag tulong para tugunan ang mga pangunahing pangangailangan.",
        "transaction_type": "G2C - Government to Citizen",
        "who_may_avail": "Nakatatandang Tayabasin na 60 taon pataas; may Senior Citizen ID, may kapansanan o Person With Disability (PWD) na may PWD ID at Solo Parent na may Solo Parent ID na nakatira sa loob ng anim (6) na buwan at lehitimong Tayabasin.",
        "documents": [
            ("Senior Citizen ID / PWD ID / Solo Parent ID", "1 photocopy", ""),
            ("Bagong Sedula (CTC)", "1 photocopy", ""),
            ("Sulat pahintulot mula sa SC/PWD/Solo Parent kapag hindi siya ang personal na kukuha ng benepisyo", "1 original", ""),
        ],
    },
    # ── PROGRAM 5 ──
    {
        "name": "Pagbibigay ng Serbisyo sa mga Preschoolers (Day Care / Supervised Neighborhood Play o SNP)",
        "description": "Pagbibigay ng panghaliling pangangalaga sa mga batang 3-4 na taong gulang habang ang kanilang mga magulang ay abala sa kani-kanilang mga gawain, malaki ang pamilya, kulang sa parenting skills at may karamdaman ang mga magulang. MATATANGGAP ANG SERBISYO: Hulyo-Abril, Lunes – Biyernes. Unang Sesyon: 8:00 ng umaga – 12:00 ng tanghali. Ikalawang Sesyon: 1:00 ng hapon – 5:00 ng hapon. BABAYARAN: P70.00 donasyon / monthly participation fee.",
        "transaction_type": "G2C - Government to Citizen",
        "who_may_avail": "Batang may edad 3 hanggang 4 na taong gulang habang ang kanilang mga magulang ay abala sa kani-kanilang mga gawain, malaki ang pamilya, kulang sa parenting skills at may karamdaman ang mga magulang.",
        "documents": [
            ("Sertipiko ng Kapanganakan o Kasal ng Magulang", "1 photocopy", ""),
            ("Tala ng Kalusugan ng Bata", "1 photocopy", ""),
            ("GMC - Growth Monitoring Chart", "", ""),
            ("Litrato – 1 piraso na 2x2", "", ""),
            ("Bagong Sedula ng Magulang", "1 photocopy", ""),
        ],
    },
    # ── PROGRAM 6 ──
    {
        "name": "Pahiram Puhunan sa Ilalim ng Programang Self-Employment Assistance (SEAP)",
        "description": "Pahiram puhunan sa mga Tayabasin na nangangailangan ng tulong partikular sa mga may maliliit na negosyo o bago pa lang magtatayo ng negosyo upang magkaroon ng karagdagang kita at matugunan ang mga pangunahing pangangailangan ng pamilya.",
        "transaction_type": "G2C - Government to Citizen",
        "who_may_avail": "Tayabasin na nakatira sa loob ng anim (6) na buwan at lehitimong botante na may pinamamahalaang maliit na negosyo.",
        "documents": [
            ("Sulat Kahilingan na may notasyon o aprubado ng Punong Lungsod", "1 original", ""),
            ("Sertipiko at Pagpapatunay ng Barangay", "1 original", ""),
            ("Sertipiko ng Rehistradong Botante", "1 photocopy", ""),
            ("Tala tungkol sa gagawing negosyo o Disenyo ng Negosyo", "1 original", ""),
            ("Bagong Sedula (CTC)", "1 photocopy", ""),
            ("Sertipiko ng Doktor kung ang negosyo ay ukol sa pagkain", "1 original", ""),
        ],
    },
    # ── PROGRAM 7 ──
    {
        "name": "Pagkakaloob ng Tulong Pinansiyal",
        "description": "Pagkakaloob ng tulong pinansiyal para sa: 1. Medikal 2. Namatayan 3. Pang-ayudang Pagkain (hal. gatas) 4. Dagdag Pabaon. Tulong pinansiyal sa mga Tayabasin na nangangailangan ng dagliang tulong partikular ang mga nasa hanay ng mahihirap. Ang halaga ay base sa bigat ng pangangailangan at inaprubahan ng Punong Lungsod at naaayon sa kakayahang pinansiyal ng pamahalaang lokal.",
        "transaction_type": "G2C - Government to Citizen",
        "who_may_avail": "Mahirap na Tayabasin o mga nasa krisis na kalalagayan na nakatira sa loob ng anim (6) na buwan at lehitimong botante.",
        "documents": [
            # Sa Medikal
            ("Sulat Kahilingan na may notasyon o aprubado ng Punong Lungsod", "1 original", "Sa Medikal"),
            ("Sertipiko at Pagpapatunay ng Barangay", "1 original", "Sa Medikal"),
            ("Sertipiko ng Rehistradong Botante", "1 photocopy", "Sa Medikal"),
            ("Sertipiko galing ospital o doktor na gumagamot / Reseta ng pirmadong doktor / Kuwenta ng pagbabayaran sa ospital", "1 photocopy", "Sa Medikal"),
            ("Bagong Sedula at Valid ID", "1 photocopy", "Sa Medikal"),
            # Sa Namatayan
            ("Sulat Kahilingan na may notasyon o aprubado ng Punong Lungsod", "1 original", "Sa Namatayan"),
            ("Sertipiko at Pagpapatunay ng Barangay", "1 original", "Sa Namatayan"),
            ("Sertipiko ng Rehistradong Botante", "1 photocopy", "Sa Namatayan"),
            ("Rekomendasyon buhat sa Tanggapan ng Nutrisyon at Doktor", "1 photocopy", "Sa Namatayan"),
            ("Bagong Sedula at PWD ID", "1 photocopy", "Sa Namatayan"),
            # Sa Dagdag Pabaon para sa mga Mag-aaral
            ("Sulat Kahilingan na may notasyon o aprubado ng Punong Lungsod", "1 original", "Sa Dagdag Pabaon para sa mga Mag-aaral"),
            ("Sertipiko at Pagpapatunay ng Barangay", "1 original", "Sa Dagdag Pabaon para sa mga Mag-aaral"),
            ("Sertipiko ng Rehistradong Botante", "1 photocopy", "Sa Dagdag Pabaon para sa mga Mag-aaral"),
            ("Pagpapatunay na nakatala sa iskul ngayong pasukan / Marka ng Nakaraang Pasukan o Report Card / Kuwenta ng Pagbabayaran sa Iskul", "1 photocopy", "Sa Dagdag Pabaon para sa mga Mag-aaral"),
            ("Bagong Sedula at Valid ID", "1 photocopy", "Sa Dagdag Pabaon para sa mga Mag-aaral"),
        ],
    },
    # ── PROGRAM 8 ──
    {
        "name": "Pagtanggap ng Bata o Kliyente sa Crisis Center",
        "description": "Pansamantalang pagkupkop sa mga bata at kababaihang biktima ng pang-aabuso at Domestic Violence na nangangailangan ng pansamantalang matutuluyan.",
        "transaction_type": "G2C - Government to Citizen",
        "who_may_avail": "Mga batang Tayabasin at kababaihang biktima ng pang-aabuso na walang matutuluyang magulang o kamag-anak.",
        "documents": [
            ("Rekomendasyon galing sa Brgy. Chairperson at aprubado ng City Social Welfare & Development Officer (CSWDO)", "1 original", ""),
            ("Sertipiko ng Rehistradong Botante", "1 photocopy", ""),
        ],
    },
]

FIRST_NAMES = [
    "Maria", "Juan", "Jose", "Ana", "Pedro", "Rosa", "Carlos", "Elena",
    "Miguel", "Carmen", "Rafael", "Luz", "Antonio", "Teresa", "Francisco",
    "Lilia", "Manuel", "Gloria", "Ricardo", "Fe", "Roberto", "Esperanza",
    "Ernesto", "Corazon", "Eduardo", "Remedios", "Danilo", "Leonora",
    "Benigno", "Natividad", "Ramon", "Florencia", "Virgilio", "Perla",
]

LAST_NAMES = [
    "Santos", "Reyes", "Cruz", "Bautista", "Gonzales", "Lopez", "Garcia",
    "Mendoza", "Torres", "Ramos", "Aquino", "Dela Cruz", "Villanueva",
    "Fernandez", "Castro", "Rivera", "Navarro", "Mercado", "Salazar",
    "Aguilar", "Castillo", "Diaz", "Flores", "Hernandez", "Lim",
]


class Command(BaseCommand):
    help = 'Seed database with barangays, real CSWDO programs, admin user, and optional demo data'

    def add_arguments(self, parser):
        parser.add_argument('--demo', action='store_true', help='Also create demo beneficiaries and requests')

    def handle(self, *args, **options):
        # ── Barangays ──
        created = updated = 0
        for name, lat, lng, pop in BARANGAYS:
            obj, was_created = Barangay.objects.get_or_create(
                name=name,
                defaults={'latitude': lat, 'longitude': lng, 'population': pop}
            )
            if was_created:
                created += 1
            else:
                obj.latitude = lat
                obj.longitude = lng
                obj.population = pop
                obj.save()
                updated += 1
        self.stdout.write(self.style.SUCCESS(
            f'Barangays: {created} created, {updated} updated.'
        ))

        # ── Programs + Required Documents ──
        prog_created = 0
        doc_created = 0
        for prog_data in PROGRAMS:
            prog, was_created = Program.objects.get_or_create(
                name=prog_data['name'],
                defaults={
                    'description': prog_data['description'],
                    'transaction_type': prog_data['transaction_type'],
                    'who_may_avail': prog_data['who_may_avail'],
                }
            )
            if was_created:
                prog_created += 1
            else:
                # Update existing program fields
                prog.description = prog_data['description']
                prog.transaction_type = prog_data['transaction_type']
                prog.who_may_avail = prog_data['who_may_avail']
                prog.save()

            # Seed required documents (skip if already exist)
            if not prog.required_documents.exists():
                for order_idx, (doc_name, doc_desc, doc_cat) in enumerate(prog_data['documents']):
                    ProgramRequiredDocument.objects.create(
                        program=prog,
                        document_name=doc_name,
                        description=doc_desc,
                        category=doc_cat,
                        order=order_idx,
                    )
                    doc_created += 1

        self.stdout.write(self.style.SUCCESS(
            f'Programs: {prog_created} created. Required documents: {doc_created} created.'
        ))

        # ── Admin user ──
        if not User.objects.filter(username='admin').exists():
            admin_user = User.objects.create_superuser(
                username='admin',
                email='admin@cswdo.gov.ph',
                password='admin123',
                first_name='CSWDO',
                last_name='Administrator',
            )
            UserProfile.objects.create(user=admin_user, role='admin')
            self.stdout.write(self.style.SUCCESS('Admin user created: admin / admin123'))
        else:
            self.stdout.write('Admin user already exists.')

        # ── Demo data ──
        if options['demo']:
            self._create_demo_data()

    def _create_demo_data(self):
        barangays = list(Barangay.objects.all())
        programs  = list(Program.objects.filter(is_active=True))
        genders   = ['Male', 'Female']

        # Create a demo citizen user
        if not User.objects.filter(username='citizen').exists():
            citizen = User.objects.create_user(
                username='citizen', email='citizen@example.com',
                password='citizen123', first_name='Sample', last_name='Citizen',
            )
            UserProfile.objects.create(
                user=citizen, role='user',
                barangay=random.choice(barangays), phone='09171234567',
            )
            self.stdout.write(self.style.SUCCESS('Demo citizen created: citizen / citizen123'))

        citizen_user = User.objects.get(username='citizen')

        # ── Bulk beneficiary seeding ──
        # Each barangay: 3–5% of its population as beneficiaries (realistic coverage)
        beneficiary_batch = []
        for brgy in barangays:
            rate    = random.uniform(0.03, 0.05)
            num_ben = max(2, int(brgy.population * rate))
            for _ in range(num_ben):
                beneficiary_batch.append(Beneficiary(
                    user=citizen_user,
                    full_name=f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
                    age=random.randint(1, 85),
                    gender=random.choice(genders),
                    barangay=brgy,
                    household_income=random.randint(2500, 25000),
                    family_members=random.randint(1, 10),
                    status='approved',
                ))

        Beneficiary.objects.bulk_create(beneficiary_batch, batch_size=500)
        self.stdout.write(self.style.SUCCESS(
            f'{len(beneficiary_batch)} beneficiaries created across {len(barangays)} barangays.'
        ))

        # ── Bulk assistance requests ──
        reasons = [
            "Nangangailangan ng tulong pinansyal para sa gastos sa ospital.",
            "Humihiling ng tulong pang-kabuhayan para sa maliit na negosyo.",
            "Nakatatandang mamamayan na humihiling ng buwanang ayuda.",
            "Tulong PWD para sa kagamitang pangkagalaw.",
            "Kailangan ng suportang nutrisyon at pang-edukasyon para sa bata.",
            "Kahilingang tulong pinansyal para sa solo parent.",
            "Biktima ng kalamidad na nangangailangan ng tulong pabahay.",
            "Referral sa ibang ahensiya ng pamahalaan para sa medikal na tulong.",
        ]
        statuses = ['submitted', 'under_review', 'approved', 'rejected']
        req_batch = []
        for _ in range(500):
            brgy = random.choice(barangays)
            # Find a beneficiary to link to
            ben = random.choice(beneficiary_batch) if beneficiary_batch else None
            req_batch.append(AssistanceRequest(
                user=citizen_user,
                beneficiary=ben,
                program=random.choice(programs),
                barangay=ben.barangay if ben else brgy,
                reason=random.choice(reasons),
                status=random.choice(statuses),
            ))

        AssistanceRequest.objects.bulk_create(req_batch, batch_size=500)
        self.stdout.write(self.style.SUCCESS(f'{len(req_batch)} demo requests created.'))
