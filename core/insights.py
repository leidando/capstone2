"""
Automated Insight Engine for CSWDO System.
Detects barangays with high beneficiary concentration, program gaps,
population-based underserved areas, vulnerability hotspots, and service gaps.
"""

from django.db.models import Count, Avg, Q
from .models import Barangay, Program, Beneficiary, AssistanceRequest


def detect_high_concentration(threshold=500):
    """Flag barangays with beneficiary count above threshold."""
    results = (
        Barangay.objects
        .annotate(total=Count('beneficiaries', filter=Q(beneficiaries__status='approved')))
        .filter(total__gt=threshold)
        .order_by('-total')
    )
    insights = []
    for b in results:
        insights.append({
            'type': 'high_concentration',
            'severity': 'warning',
            'icon': '⚠️',
            'barangay': b.name,
            'value': b.total,
            'message': (
                f'Barangay {b.name} has {b.total} beneficiaries '
                f'(exceeds threshold of {threshold}). '
                f'Consider allocating additional resources.'
            ),
        })
    return insights


def detect_program_gaps(min_total=30, gap_threshold=5):
    """
    For each barangay that has at least `min_total` beneficiaries,
    detect programs with fewer than `gap_threshold` beneficiaries.
    """
    active_programs = Program.objects.filter(is_active=True)
    barangays = (
        Barangay.objects
        .annotate(total=Count('beneficiaries', filter=Q(beneficiaries__status='approved')))
        .filter(total__gte=min_total)
    )

    insights = []
    for brgy in barangays:
        program_counts = (
            AssistanceRequest.objects
            .filter(barangay=brgy, status='approved')
            .values('program__name')
            .annotate(count=Count('id'))
        )
        program_map = {pc['program__name']: pc['count'] for pc in program_counts}

        for prog in active_programs:
            count = program_map.get(prog.name, 0)
            if count < gap_threshold:
                insights.append({
                    'type': 'program_gap',
                    'severity': 'danger',
                    'icon': '🔴',
                    'barangay': brgy.name,
                    'program': prog.name,
                    'value': count,
                    'total': brgy.total,
                    'message': (
                        f'Barangay {brgy.name} has {brgy.total} total beneficiaries '
                        f'but only {count} in {prog.name}. '
                        f'Health/welfare services may be insufficient.'
                    ),
                })
    return insights


def detect_population_gaps(coverage_rate=0.02):
    """
    Flag barangays where actual beneficiaries are far below expected
    based on population. Expected = population * coverage_rate.
    Returns a list of dicts (also usable by the gap API endpoint).
    """
    barangays = (
        Barangay.objects
        .annotate(total=Count('beneficiaries', filter=Q(beneficiaries__status='approved')))
        .filter(population__gt=0)
        .order_by('-population')
    )

    gaps = []
    for b in barangays:
        expected = int(b.population * coverage_rate)
        actual = b.total
        gap = max(0, expected - actual)
        if gap > 0:
            gaps.append({
                'type': 'population_gap',
                'severity': 'info',
                'icon': '📊',
                'barangay': b.name,
                'population': b.population,
                'expected': expected,
                'actual': actual,
                'gap': gap,
                'message': (
                    f'Barangay {b.name} — Population: {b.population:,}, '
                    f'Expected beneficiaries: {expected}, '
                    f'Registered: {actual}. '
                    f'Estimated gap: {gap} individuals.'
                ),
            })
    return gaps


def detect_vulnerability_hotspots():
    """Flag barangays with high average vulnerability scores."""
    barangays = (
        Barangay.objects
        .annotate(
            avg_vuln=Avg('beneficiaries__vulnerability_score',
                         filter=Q(beneficiaries__status='approved')),
            total=Count('beneficiaries', filter=Q(beneficiaries__status='approved')),
            high_risk=Count('beneficiaries',
                            filter=Q(beneficiaries__status='approved',
                                     beneficiaries__vulnerability_level__in=['high', 'critical'])),
        )
        .filter(avg_vuln__isnull=False, avg_vuln__gt=40, total__gte=3)
        .order_by('-avg_vuln')
    )

    insights = []
    for b in barangays:
        severity = 'danger' if b.avg_vuln >= 60 else 'warning'
        icon = '🔴' if b.avg_vuln >= 60 else '🟡'
        insights.append({
            'type': 'vulnerability_hotspot',
            'severity': severity,
            'icon': icon,
            'barangay': b.name,
            'value': round(b.avg_vuln, 1),
            'high_risk': b.high_risk,
            'total': b.total,
            'message': (
                f'Barangay {b.name} has an average vulnerability score of '
                f'{b.avg_vuln:.1f}/100 with {b.high_risk} high-risk individuals '
                f'out of {b.total} beneficiaries. Prioritize outreach and services.'
            ),
        })
    return insights


def detect_service_gaps():
    """
    Flag barangays where service gap index is high.
    Service Gap Index = total_beneficiaries / total_services_provided.
    Higher value = more beneficiaries not getting services.
    """
    barangays = (
        Barangay.objects
        .annotate(
            total_bens=Count('beneficiaries', filter=Q(beneficiaries__status='approved')),
            total_services=Count('requests', filter=Q(requests__status='approved')),
        )
        .filter(total_bens__gt=0)
        .order_by('-total_bens')
    )

    insights = []
    for b in barangays:
        services = max(b.total_services, 1)
        sgi = round(b.total_bens / services, 2)
        if sgi > 3:
            severity = 'danger' if sgi > 5 else 'warning'
            icon = '🔴' if sgi > 5 else '🟡'
            insights.append({
                'type': 'service_gap',
                'severity': severity,
                'icon': icon,
                'barangay': b.name,
                'value': sgi,
                'total_bens': b.total_bens,
                'total_services': b.total_services,
                'message': (
                    f'Barangay {b.name} has a Service Gap Index of {sgi} '
                    f'({b.total_bens} beneficiaries / {b.total_services} services). '
                    f'{"Requires urgent additional services." if sgi > 5 else "Consider expanding program coverage."}'
                ),
            })
    return insights


def detect_overloaded_programs(threshold=0.6):
    """Flag programs where pending requests exceed approved requests."""
    programs = Program.objects.filter(is_active=True).annotate(
        total=Count('requests'),
        pending=Count('requests', filter=Q(requests__status__in=['submitted', 'under_review'])),
        approved=Count('requests', filter=Q(requests__status='approved')),
    ).filter(total__gte=5)

    insights = []
    for p in programs:
        if p.total > 0 and (p.pending / p.total) > threshold:
            insights.append({
                'type': 'overloaded_program',
                'severity': 'warning',
                'icon': '⚠️',
                'program': p.name,
                'barangay': 'System-wide',
                'value': p.pending,
                'total': p.total,
                'message': (
                    f'Program "{p.name}" has {p.pending} pending requests out of '
                    f'{p.total} total ({p.pending * 100 // p.total}% pending). '
                    f'Consider assigning additional staff.'
                ),
            })
    return insights


def detect_elderly_vulnerability():
    """Flag barangays with high concentration of elderly vulnerable beneficiaries."""
    barangays = (
        Barangay.objects
        .annotate(
            elderly_high_risk=Count(
                'beneficiaries',
                filter=Q(
                    beneficiaries__status='approved',
                    beneficiaries__age__gte=60,
                    beneficiaries__vulnerability_level__in=['high', 'critical']
                )
            ),
            total=Count('beneficiaries', filter=Q(beneficiaries__status='approved')),
        )
        .filter(elderly_high_risk__gte=3)
        .order_by('-elderly_high_risk')
    )

    insights = []
    for b in barangays:
        insights.append({
            'type': 'elderly_vulnerability',
            'severity': 'danger',
            'icon': '👴',
            'barangay': b.name,
            'value': b.elderly_high_risk,
            'total': b.total,
            'message': (
                f'Barangay {b.name} has {b.elderly_high_risk} elderly individuals '
                f'(age 60+) with high/critical vulnerability. '
                f'Prioritize senior citizen welfare programs.'
            ),
        })
    return insights


def generate_all_insights():
    """Return combined list of all automated insights."""
    insights = []
    insights.extend(detect_high_concentration(threshold=100))
    insights.extend(detect_program_gaps(min_total=30, gap_threshold=5))

    # Population-based: only show top 5 most underserved to avoid dashboard flooding
    pop_gaps = detect_population_gaps(coverage_rate=0.05)
    for g in pop_gaps[:5]:
        insights.append({
            'type': g['type'],
            'severity': g['severity'],
            'icon': g['icon'],
            'barangay': g['barangay'],
            'population': g.get('population', 0),
            'value': g['gap'],
            'message': g['message'],
        })

    # Vulnerability-based insights
    insights.extend(detect_vulnerability_hotspots()[:10])
    insights.extend(detect_service_gaps()[:10])
    insights.extend(detect_overloaded_programs())
    insights.extend(detect_elderly_vulnerability()[:5])

    return insights
