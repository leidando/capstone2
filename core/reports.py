"""
Report generation utilities for CSWDO admin exports.
Produces CSV content for barangay and program reports.
"""
import csv
import io
from django.db.models import Count, Avg, Q
from .models import Barangay, Program, Beneficiary, AssistanceRequest


def generate_barangay_report():
    """Return CSV string for barangay-level analytics."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        'Barangay', 'Population', 'Total Beneficiaries', 'Avg Vulnerability Score',
        'High-Risk Count', 'Total Requests', 'Approved Requests',
        'Service Gap Index', 'Recommendation',
    ])

    barangays = Barangay.objects.all().order_by('name')
    for b in barangays:
        bens = Beneficiary.objects.filter(barangay=b, status='approved')
        ben_count = bens.count()
        avg_vuln = bens.aggregate(avg=Avg('vulnerability_score'))['avg'] or 0
        high_risk = bens.filter(vulnerability_level__in=['high', 'critical']).count()
        total_reqs = AssistanceRequest.objects.filter(barangay=b).count()
        approved_reqs = AssistanceRequest.objects.filter(barangay=b, status='approved').count()
        sgi = round(ben_count / max(approved_reqs, 1), 2)

        rec = ''
        if sgi > 5:
            rec = 'Requires more services — high service gap'
        elif avg_vuln > 50:
            rec = 'High vulnerability — prioritize outreach'
        elif ben_count == 0:
            rec = 'No registered beneficiaries — needs survey'

        writer.writerow([
            b.name, b.population, ben_count, round(avg_vuln, 2),
            high_risk, total_reqs, approved_reqs, sgi, rec,
        ])

    return buf.getvalue()


def generate_program_report():
    """Return CSV string for program-level analytics."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        'Program', 'Total Requests', 'Approved', 'Rejected', 'Pending',
        'Unique Beneficiaries', 'Avg Vulnerability Score', 'Effectiveness %', 'Recommendation',
    ])

    programs = Program.objects.filter(is_active=True).order_by('name')
    for p in programs:
        reqs = AssistanceRequest.objects.filter(program=p)
        total = reqs.count()
        approved = reqs.filter(status='approved').count()
        rejected = reqs.filter(status='rejected').count()
        pending = reqs.filter(status__in=['submitted', 'under_review']).count()
        unique_bens = reqs.filter(beneficiary__isnull=False).values('beneficiary').distinct().count()

        avg_vuln = Beneficiary.objects.filter(
            requests__program=p, status='approved'
        ).aggregate(avg=Avg('vulnerability_score'))['avg'] or 0

        effectiveness = round((approved / max(total, 1)) * 100, 1)

        rec = ''
        if pending > approved and total > 10:
            rec = 'Program may be overloaded — review staffing'
        elif effectiveness < 30 and total > 5:
            rec = 'Low approval rate — review eligibility criteria'
        elif avg_vuln > 60:
            rec = 'Serving highly vulnerable population — maintain priority'

        writer.writerow([
            p.name, total, approved, rejected, pending,
            unique_bens, round(avg_vuln, 2), effectiveness, rec,
        ])

    return buf.getvalue()


def _render_pdf(html_string):
    """Convert HTML string to PDF bytes using xhtml2pdf."""
    from xhtml2pdf import pisa
    buf = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.StringIO(html_string), dest=buf)
    if pisa_status.err:
        return None
    return buf.getvalue()


_PDF_STYLE = """
<style>
    @page { size: landscape; margin: 1.5cm; }
    body { font-family: Helvetica, Arial, sans-serif; font-size: 9px; color: #1e293b; }
    h1 { font-size: 16px; color: #001F3F; margin-bottom: 4px; }
    .subtitle { font-size: 10px; color: #64748b; margin-bottom: 16px; }
    table { width: 100%; border-collapse: collapse; margin-top: 8px; }
    th { background-color: #001F3F; color: #ffffff; padding: 6px 8px; text-align: left; font-size: 8px; text-transform: uppercase; letter-spacing: 0.5px; }
    td { padding: 5px 8px; border-bottom: 1px solid #e2e8f0; font-size: 8px; }
    tr:nth-child(even) td { background: #f8fafc; }
    .danger { color: #ef4444; font-weight: bold; }
    .warning { color: #f59e0b; font-weight: bold; }
    .success { color: #22c55e; font-weight: bold; }
    .footer { text-align: center; font-size: 7px; color: #94a3b8; margin-top: 16px; }
</style>
"""


def generate_barangay_report_pdf():
    """Return PDF bytes for barangay-level analytics."""
    from django.utils import timezone

    barangays = Barangay.objects.all().order_by('name')
    rows = ''
    for b in barangays:
        bens = Beneficiary.objects.filter(barangay=b, status='approved')
        ben_count = bens.count()
        avg_vuln = bens.aggregate(avg=Avg('vulnerability_score'))['avg'] or 0
        high_risk = bens.filter(vulnerability_level__in=['high', 'critical']).count()
        total_reqs = AssistanceRequest.objects.filter(barangay=b).count()
        approved_reqs = AssistanceRequest.objects.filter(barangay=b, status='approved').count()
        sgi = round(ben_count / max(approved_reqs, 1), 2)

        vuln_class = 'danger' if avg_vuln >= 60 else 'warning' if avg_vuln >= 40 else ''
        sgi_class = 'danger' if sgi > 5 else 'warning' if sgi > 3 else 'success'

        rec = ''
        if sgi > 5:
            rec = 'Requires more services'
        elif avg_vuln > 50:
            rec = 'Prioritize outreach'
        elif ben_count == 0:
            rec = 'Needs survey'

        rows += f'''<tr>
            <td><strong>{b.name}</strong></td><td>{b.population or 'N/A'}</td>
            <td>{ben_count}</td><td class="{vuln_class}">{round(avg_vuln, 1)}</td>
            <td class="danger">{high_risk}</td><td>{total_reqs}</td><td>{approved_reqs}</td>
            <td class="{sgi_class}">{sgi}</td><td>{rec}</td>
        </tr>'''

    html = f'''<html><head>{_PDF_STYLE}</head><body>
        <h1>CSWDO Barangay Analytics Report</h1>
        <div class="subtitle">Tayabas City, Quezon &mdash; Generated {timezone.now().strftime("%B %d, %Y %I:%M %p")}</div>
        <table>
            <thead><tr>
                <th>Barangay</th><th>Population</th><th>Beneficiaries</th><th>Avg Vuln.</th>
                <th>High-Risk</th><th>Requests</th><th>Approved</th><th>SGI</th><th>Recommendation</th>
            </tr></thead>
            <tbody>{rows}</tbody>
        </table>
        <div class="footer">City Social Welfare &amp; Development Office &mdash; Confidential Government Document</div>
    </body></html>'''
    return _render_pdf(html)


def generate_program_report_pdf():
    """Return PDF bytes for program-level analytics."""
    from django.utils import timezone

    programs = Program.objects.filter(is_active=True).order_by('name')
    rows = ''
    for p in programs:
        reqs = AssistanceRequest.objects.filter(program=p)
        total = reqs.count()
        approved = reqs.filter(status='approved').count()
        rejected = reqs.filter(status='rejected').count()
        pending = reqs.filter(status__in=['submitted', 'under_review']).count()
        unique_bens = reqs.filter(beneficiary__isnull=False).values('beneficiary').distinct().count()
        avg_vuln = Beneficiary.objects.filter(
            requests__program=p, status='approved'
        ).aggregate(avg=Avg('vulnerability_score'))['avg'] or 0
        effectiveness = round((approved / max(total, 1)) * 100, 1)

        eff_class = 'success' if effectiveness >= 70 else 'warning' if effectiveness >= 40 else 'danger'

        rec = ''
        if pending > approved and total > 10:
            rec = 'Review staffing'
        elif effectiveness < 30 and total > 5:
            rec = 'Review eligibility'
        elif avg_vuln > 60:
            rec = 'Maintain priority'

        rows += f'''<tr>
            <td><strong>{p.name}</strong></td><td>{total}</td><td>{approved}</td>
            <td>{rejected}</td><td>{pending}</td><td>{unique_bens}</td>
            <td>{round(avg_vuln, 1)}</td><td class="{eff_class}">{effectiveness}%</td><td>{rec}</td>
        </tr>'''

    html = f'''<html><head>{_PDF_STYLE}</head><body>
        <h1>CSWDO Program Effectiveness Report</h1>
        <div class="subtitle">Tayabas City, Quezon &mdash; Generated {timezone.now().strftime("%B %d, %Y %I:%M %p")}</div>
        <table>
            <thead><tr>
                <th>Program</th><th>Requests</th><th>Approved</th><th>Rejected</th>
                <th>Pending</th><th>Unique Bens.</th><th>Avg Vuln.</th><th>Effectiveness</th><th>Recommendation</th>
            </tr></thead>
            <tbody>{rows}</tbody>
        </table>
        <div class="footer">City Social Welfare &amp; Development Office &mdash; Confidential Government Document</div>
    </body></html>'''
    return _render_pdf(html)
