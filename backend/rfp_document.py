"""The agent's input: one RFP, as plain text.

In the real product this is whatever the ingestion pipeline hands the agent. Here
it is a fixture, so the POC runs with no upstream and so two runs are comparable.

The content is deliberately uneven -- §4 states no budget, the incumbent question
is left open, and the evaluation weighting is vague. That is the point: a section
that renders identically no matter what it reads has not demonstrated anything.
The unstated budget is what should earn a coral `signal` band, and it should do so
because the model noticed, not because we hardcoded it.
"""

from __future__ import annotations

# Matches the header in the design mock: Cedar Wellness · Healthcare · T-1049.
RFP_TITLE = "Cedar Wellness — Patient Engagement RFP"
RFP_CLIENT = "Cedar Wellness"
RFP_SECTOR = "Healthcare"
RFP_REFERENCE = "T-1049"

RFP_TEXT = """\
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
"""


def rfp_for_prompt() -> str:
    """Render the RFP for inclusion in a system prompt."""
    return (
        f"{RFP_TITLE}\n"
        f"Client: {RFP_CLIENT} · Sector: {RFP_SECTOR} · Reference: {RFP_REFERENCE}\n\n"
        f"{RFP_TEXT}"
    )
