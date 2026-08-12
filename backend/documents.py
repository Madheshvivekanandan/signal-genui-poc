"""The agent's input: four documents, as fixtures.

In the real product this is whatever the ingestion pipeline hands the agent.
Here they are fixtures, so the POC runs with no upstream and so two runs are
comparable.

**These four exist to produce four visibly different interfaces from one closed
catalog.** That is the claim the POC has to survive, and a set of documents that
all read the same way would never test it. Each is shaped to force a different
answer to "which components does this deserve?":

| Document      | What it states                          | Expected shape |
|---------------|-----------------------------------------|----------------|
| cedar-wellness| Rich, but no budget and no weightings   | Grid + intel bands + a budget risk |
| meridian      | Published weightings AND a real budget  | Grid + a score_table; little to flag |
| northwind     | Almost nothing -- an RFI, not an RFP    | Few molecules, mostly risk |
| halcyon       | Dense, highly specified, tightly run    | Many sourced context bands |

The shapes are *expected*, not enforced. Nothing here tells the agent what to
draw; the documents differ and the agent responds. If a run comes back with a
shape not in this table that is a finding, not a bug -- and it is worth reading
the document again before assuming the model was wrong.
"""

from __future__ import annotations

from dataclasses import dataclass

# The header of the RFP Overview screen is not generated -- these facts come from
# the record. Kept beside the body so a document is one object, not four parallel
# constants that can drift.


@dataclass(frozen=True)
class Document:
    """One analysable document, plus the header facts the page shows above it."""

    key: str
    title: str
    client: str
    sector: str
    reference: str
    # One line for the picker, so a demo can say what to expect before running it.
    expect: str
    body: str

    def for_prompt(self) -> str:
        """Render the document for inclusion in a system prompt."""
        return (
            f"{self.title}\n"
            f"Client: {self.client} · Sector: {self.sector} · Reference: {self.reference}\n\n"
            f"{self.body}"
        )


CEDAR = Document(
    key="cedar-wellness",
    title="Cedar Wellness — Patient Engagement RFP",
    client="Cedar Wellness",
    sector="Healthcare",
    reference="T-1049",
    expect="Rich but incomplete — no budget, no weightings. Expect a risk band.",
    body="""\
REQUEST FOR PROPOSAL — T-1049
Cedar Wellness Group · Patient Engagement Partner
Issued 14 July 2026

§1 · BACKGROUND

Cedar Wellness Group operates 34 outpatient clinics across five states, with
concentrations in cardiology and oncology. Board minutes published in our 2025
annual report name patient engagement as a primary revenue lever, distinct from
continued clinical capital investment.

Our internal review found that clinical teams spend approximately 27% of their
time on administrative tasks that patients could complete themselves. Staffing
attrition attributed to administrative load is a named risk factor in our most
recent Item 1A disclosure.

§2 · WHAT WE ARE ASKING FOR

We are seeking an integrated, outcomes-led partner to grow direct bookings across
our prioritised service lines. Scope spans performance media, lifecycle and CRM,
and brand. We are explicit that we will measure this engagement on commercial
growth — booked appointments and attributed service-line revenue — and not on
channel reporting or media efficiency metrics.

Respondents proposing a channel-execution-only engagement will not be advanced.

§3 · TIMELINE AND PROCESS

Written responses are due within 14 calendar days of this document's issue date.
A shortlist of no more than four respondents will be invited to present. A single
point of contact is named in Appendix A for all clarification questions; direct
outreach to clinic leadership or to board members during the evaluation period
will disqualify a respondent.

Presentations are expected in the week following shortlisting. Contract award is
targeted for early September.

§4 · COMMERCIAL

Respondents should price at competitive market rates for a twelve-month
engagement with an option to extend. We have not published a budget envelope for
this engagement and do not intend to.

Fee structure is at the respondent's discretion, though our procurement function
has a documented preference for fixed-fee phasing over time-and-materials
arrangements. Proposals structured as open-ended time-and-materials will require
additional legal review, which the timeline above does not accommodate.

§5 · KEY REQUIREMENTS

Responses must include:

  (a) A named senior team, with the individuals who will hold the account
      identified by name and role. Substitution after award requires written
      approval.
  (b) Measurable KPIs tied to the commercial outcomes in §2, with baselines
      stated.
  (c) A phased delivery plan with defined entry and exit criteria per phase.
  (d) Three client references, at least one in a regulated sector.
  (e) One comparable case study, with outcomes attributed and verifiable.

§6 · EVALUATION

Responses will be evaluated on strategic fit, demonstrated outcomes in comparable
engagements, team credibility, and commercial terms. The evaluation panel will
comprise the Chief Digital Officer, the Head of Procurement, and two service-line
clinical leads.

Relative weighting of the evaluation criteria is at the panel's discretion.

§7 · INCUMBENT

Cedar Wellness has worked with a media agency of record since 2023. The scope of
that relationship, and whether it continues alongside this engagement, is not
addressed in this document.
""",
)


MERIDIAN = Document(
    key="meridian-health",
    title="Meridian Health — Digital Care Platform",
    client="Meridian Health",
    sector="Healthcare",
    reference="M-2210",
    expect="States its weightings and its budget. Expect a scored table.",
    body="""\
INVITATION TO TENDER — M-2210
Meridian Health Trust · Digital Care Platform
Issued 2 August 2026

§1 · SCOPE

Meridian Health Trust will replace its incumbent patient portal across 18 sites.
The replacement must cover appointment self-service, results delivery, secure
messaging, and pre-attendance questionnaires. Migration of 1.4 million active
patient records is in scope.

§2 · EVALUATION CRITERIA AND WEIGHTINGS

Responses are scored out of 5.0 against the published weightings below. The panel
will publish scores to all respondents after award.

  Clinical safety and regulatory compliance ....... 30%
  Integration with the existing EHR (Epic) ........ 25%
  Total cost of ownership over five years ......... 20%
  Implementation track record in the NHS .......... 15%
  Accessibility, WCAG 2.2 AA conformance .......... 10%

A weighted score below 3.0 in any single criterion disqualifies a response
regardless of the total. The minimum passing weighted total is 3.5.

§3 · COMMERCIAL

The published budget envelope is £850,000 to £1,100,000 over three years,
inclusive of migration and first-year support. Responses outside this envelope
will not be scored. Payment is milestone-linked against §5.

§4 · TIMELINE

Responses are due within 21 calendar days. Clarification questions close at day
10 and answers are published to all respondents. Award is targeted within 60 days
of the response deadline. Service commencement is 1 February 2027.

§5 · MANDATORY REQUIREMENTS

  (a) DSPT compliance, evidenced, at the time of response.
  (b) Two NHS trust references at comparable scale, contactable.
  (c) A named clinical safety officer holding DCB0129 accountability.
  (d) A migration plan with a documented rollback position.

§6 · INCUMBENT

The incumbent supplier is named: Calder Systems, in place since 2019. Their
contract expires 31 January 2027 and will not be extended. Meridian confirms the
incumbent has been invited to tender on the same terms as all other respondents.
""",
)


NORTHWIND = Document(
    key="northwind-logistics",
    title="Northwind Logistics — Driver Scheduling RFI",
    client="Northwind Logistics",
    sector="Transport",
    reference="NW-04",
    expect="An RFI that states almost nothing. Expect a short, heavily flagged read.",
    body="""\
REQUEST FOR INFORMATION — NW-04
Northwind Logistics · Driver Scheduling
Issued 8 August 2026

§1 · PURPOSE

Northwind Logistics is exploring options for a driver scheduling tool. This is a
request for information, not a request for proposal. No commitment to procure is
made or implied by this document.

§2 · WHAT WE WOULD LIKE

A short capability overview and two customer references. One page is sufficient.
We would prefer not to receive pricing at this stage.

§3 · WHAT WE HAVE NOT DECIDED

Budget has not been set. No timeline has been agreed. Evaluation criteria have
not been defined, and no evaluation panel has been convened. Whether this
proceeds to a formal tender is subject to a board decision in Q4, which has not
been scheduled.

§4 · CONTACT

Responses to the procurement mailbox. We will not be answering clarification
questions at the RFI stage.
""",
)


HALCYON = Document(
    key="halcyon-bank",
    title="Halcyon Bank — Regulatory Reporting Platform",
    client="Halcyon Bank",
    sector="Financial services",
    reference="HB-7731",
    expect="Dense and highly specified. Expect many sourced findings.",
    body="""\
REQUEST FOR PROPOSAL — HB-7731
Halcyon Bank plc · Regulatory Reporting Platform
Issued 21 July 2026

§1 · BACKGROUND

Halcyon Bank plc reports under CRR III and submits COREP and FINREP returns to
the PRA on a quarterly basis. A 2025 s166 skilled person review identified
manual intervention in the reporting chain as a control weakness. Remediation is
committed to the regulator with a hard completion date of 31 December 2027.

§2 · SCOPE

A platform that ingests from the existing data warehouse, applies the regulatory
calculation layer, produces validated returns in the regulator's schema, and
retains a full audit trail with lineage from submitted figure back to source
record. In scope: COREP, FINREP, Pillar 3 disclosures. Out of scope: IFRS 9
provisioning models, which are being replaced under a separate programme.

§3 · TIMELINE

Responses due within 30 calendar days. Shortlisting within 10 working days of
close. Proof of concept required from shortlisted respondents, at their own cost,
against a supplied anonymised dataset. Award targeted for 15 November 2026 with
implementation beginning January 2027.

§4 · COMMERCIAL

Budget is approved at £4.2m capital and £900k annual run cost, sourced from the
2027 change portfolio. The bank will contract on its own paper. A 10% holdback
against successful regulatory submission for two consecutive quarters applies and
is not negotiable.

§5 · MANDATORY REQUIREMENTS

  (a) Demonstrable CRR III calculation coverage at the time of response, not on a
      roadmap.
  (b) Two UK banking references of comparable balance sheet size.
  (c) Full data lineage, field level, from submitted return to source system.
  (d) UK data residency, with no processing outside the UK.
  (e) SOC 2 Type II, current, provided at response.
  (f) Exit assistance provisions of no less than 12 months.

§6 · EVALUATION AND PROCESS

Evaluation is by a panel chaired by the Group Head of Regulatory Reporting, with
representation from Technology, Procurement, and the second line risk function.
The bank operates a formal conflict-of-interest declaration; any respondent with
a current engagement in the second line must declare it at response.

§7 · INCUMBENT AND CONTEXT

The current returns are produced on an in-house platform built in 2014, extended
repeatedly, and now supported by two named individuals. Key person risk on that
platform is on the bank's operational risk register. There is no incumbent vendor
to displace.
""",
)


DOCUMENTS: dict[str, Document] = {
    document.key: document for document in (CEDAR, MERIDIAN, NORTHWIND, HALCYON)
}

# Cedar is the default because the design mock and the README's screenshots are of
# that screen; a demo that opens on anything else stops matching the reference.
DEFAULT_KEY = CEDAR.key


def get(key: str | None) -> Document:
    """Look up a document, falling back to the default.

    Falls back rather than raising: the key arrives from a query string, and an
    unknown one should render the demo's front door, not a 4xx the page has no
    way to draw.
    """
    return DOCUMENTS.get(key or DEFAULT_KEY, CEDAR)
