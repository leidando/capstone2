import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cswdo_system.settings')
django.setup()

from core.models import Barangay, Program, ProgramRequiredDocument

def seed_data():
    print("🧹 Cleaning existing data (Barangays and Programs)...")
    # We use get_or_create to avoid duplicates, but for a clean seed we can delete if needed.
    # For a safe seeder, we just use get_or_create.

    # 1. Seed Barangays (74 real barangays from Tayabas City)
    barangays = [
        'Alitao', 'Alsam Ibaba', 'Alsam Ilaya', 'Alupay', 'Angeles Zone I (Pob.)', 
        'Angeles Zone II', 'Angeles Zone III', 'Angeles Zone IV', 
        'Angustias Zone I (Pob.)', 'Angustias Zone II', 'Angustias Zone III', 'Angustias Zone IV', 
        'Anos', 'Ayaas', 'Baguio', 'Banilad', 'Bukal Ibaba', 'Bukal Ilaya', 
        'Calantas', 'Calumpang', 'Camaysa', 'Dapdap', 'Domoit', 'Domoit Kanluran', 
        'Domoit Silangan', 'Gibanga', 'Ibabang Bukal', 'Ibas', 'Ilasan Ibaba', 
        'Ilasan Ilaya', 'Ipilan', 'Isabang', 'Katigan Kanluran', 'Katigan Silangan', 
        'Lakawan', 'Lalo', 'Lawigue', 'Lita (Pob.)', 'Malao-a', 'Malaoa', 'Masin', 
        'Mate', 'Mateuna', 'Mayowe', 'Nangka Ibaba', 'Nangka Ilaya', 'Opias', 
        'Palale', 'Palale Ibaba', 'Palale Ilaya', 'Palale Kanluran', 'Palale Silangan', 
        'Pandakaki', 'Pook', 'Potol', 'San Diego', 'San Diego Zone I (Pob.)', 
        'San Diego Zone II', 'San Diego Zone III', 'San Diego Zone IV', 'San Isidro', 
        'San Isidro Zone I (Pob.)', 'San Isidro Zone II', 'San Isidro Zone III', 
        'San Isidro Zone IV', 'San Roque', 'San Roque Zone I (Pob.)', 'San Roque Zone II', 
        'Talolong', 'Tamlong', 'Tongko', 'Valencia', 'Wakas'
    ]

    print(f"📍 Seeding {len(barangays)} Barangays...")
    for b_name in barangays:
        Barangay.objects.get_or_create(
            name=b_name,
            defaults={'latitude': 14.0200, 'longitude': 121.5800, 'population': 0}
        )

    # 2. Seed Core CSWDO Programs
    programs_data = [
        {
            'name': 'Pagkakaloob ng Tulong Pinansiyal',
            'description': 'Pagkakaloob ng tulong pinansiyal para sa: 1. Medikal 2. Namatayan 3. Pang-ayudang Pagkain (hal. gatas) 4. Dagdag Pabaon. Tulong pinansiyal sa mga Tayabasin na nangangailangan ng dagliang tulong partikular ang mga nasa hanay ng mahihirap.',
            'transaction_type': 'G2C - Government to Citizen',
            'who_may_avail': 'Indigents, Senior Citizens, PWDs, Solo Parents'
        },
        {
            'name': 'Pagbibigay Tulong Pinansyal sa Pagsasaayos ng Bahay sa mga Nasalanta ng Kalamidad (Sunog, Bagyo, Baha at Iba Pa)',
            'description': 'Pagkakaloob ng daglian tulong pabahay (Emergency Shelter Assistance) sa mga Tayabasing biktima ng kalamidad (sunog, bagyo, baha at iba pa).',
            'transaction_type': 'G2C - Government to Citizen',
            'who_may_avail': 'Victims of Calamity'
        },
        {
            'name': 'Pagbibigay ng Social Case Study Report para Makahingi ng Tulong sa Ibang Ahensiya ng Pamahalaan ang mga Tayabasin (Referral Services)',
            'description': 'Pagsasagawa ng Social Case Study Report para sa mga Tayabasin na nangangailangan ng tulong partikular ang mga nasa hanay ng mahihirap upang makahingi sa ibang ahensiya ng pamahalaan ng tulong depende sa kanilang inilalapit na kahilingan (PCSO, QMC, OPSWD, Office of the Congressman, Government Hospitals outside Quezon).',
            'transaction_type': 'G2C - Government to Citizen',
            'who_may_avail': 'Indigent Citizens'
        },
        {
            'name': 'Pagkakaloob ng Nationally Uniformed ID sa mga Nakatatandang Mamamayan (Senior Citizens), sa mga Taong May Kapansanan (PWD) at sa mga Solo Parent',
            'description': 'Bilang pagtupad sa itinakda ng batas ang bawat nakatatandang mamamayan, may kapansanan (PWD) at Solo Parent ay kailangang pagkalooban ng ID upang pakinabangan ang mga pribiliheyo at benepisyong nakapaloob dito.',
            'transaction_type': 'G2C - Government to Citizen',
            'who_may_avail': 'Senior Citizens (60+), PWDs, Solo Parents'
        },
        {
            'name': 'Pagkakaloob ng Tulong Pinansiyal para sa mga Lolo at Lola (Senior Citizens) at Person with Disabilities (PWD)',
            'description': 'Espesyal na serbisyong ipinagkakaloob kay lolo at lola, may kapansanan o Person With Disability (PWD) at Solo Parent na nagdaos ng kanilang kaarawan bilang dagdag tulong para tugunan ang mga pangunahing pangangailangan.',
            'transaction_type': 'G2C - Government to Citizen',
            'who_may_avail': 'Birthday celebrants (Senior/PWD/Solo Parent)'
        },
        {
            'name': 'Pagbibigay ng Serbisyo sa mga Preschoolers (Day Care / Supervised Neighborhood Play o SNP)',
            'description': 'Pagbibigay ng panghaliling pangangalaga sa mga batang 3-4 na taong gulang habang ang kanilang mga magulang ay abala sa kani-kanilang mga gawain, malaki ang pamilya, kulang sa parenting skills at may karamdaman ang mga magulang.',
            'transaction_type': 'G2C - Government to Citizen',
            'who_may_avail': 'Preschool children (3-4 years old)'
        },
        {
            'name': 'Pahiram Puhunan sa Ilalim ng Programang Self-Employment Assistance (SEAP)',
            'description': 'Pahiram puhunan sa mga Tayabasin na nangangailangan ng tulong partikular sa mga may maliliit na negosyo o bago pa lang magtatayo ng negosyo upang magkaroon ng karagdagang kita.',
            'transaction_type': 'G2B - Government to Business / Citizen',
            'who_may_avail': 'Micro-entrepreneurs'
        },
        {
            'name': 'Pagtanggap ng Bata o Kliyente sa Crisis Center',
            'description': 'Pansamantalang pagkupkop sa mga bata at kababaihang biktima ng pang-aabuso at Domestic Violence na nangangailangan ng pansamantalang matutuluyan.',
            'transaction_type': 'G2C - Government to Citizen',
            'who_may_avail': 'Victims of Abuse/Domestic Violence'
        }
    ]

    print(f"📁 Seeding {len(programs_data)} Programs...")
    for p_data in programs_data:
        prog, created = Program.objects.get_or_create(
            name=p_data['name'],
            defaults={
                'description': p_data['description'],
                'transaction_type': p_data['transaction_type'],
                'who_may_avail': p_data['who_may_avail']
            }
        )
        
        # Add basic documents for all programs as a fallback
        docs = ['Valid ID', 'Barangay Indigency', 'Certificate of Residency', 'Letter of Request']
        for doc_name in docs:
            ProgramRequiredDocument.objects.get_or_create(
                program=prog,
                document_name=doc_name,
                defaults={'category': 'Identipikasyon', 'is_required': True}
            )

    print("✅ Seeding complete!")

if __name__ == "__main__":
    seed_data()
