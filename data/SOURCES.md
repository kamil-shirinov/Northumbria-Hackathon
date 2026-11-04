# Data sources

All values in `careers.csv` and `courses.csv` come from these public pages, fetched on 4 November 2026. Nothing was filled in from memory. Where a value needed a judgement call (a skill mapping, a unit conversion), it is noted below.

## Careers (careers.csv)

Each career's `pay_min`/`pay_max` is the "Average salary (a year)" starter-to-experienced range on its National Careers Service (NCS) job profile, and that profile is its `source_url`. The five entry routes paraphrase the profile's "How to become" section (college, apprenticeship, work, volunteering, direct application, other routes, career tips). The skills are short names for items in the profile's "What it takes" list, plus a role's core technical skill named in "How to become" (for example electrical installation, welding).

| ID | Career | Pay (£ a year) | NCS job profile |
| --- | --- | --- | --- |
| CAR01 | Healthcare assistant | 25,000–27,000 | https://nationalcareers.service.gov.uk/job-profiles/healthcare-assistant |
| CAR02 | Care worker | 20,000–25,000 | https://nationalcareers.service.gov.uk/job-profiles/care-worker |
| CAR03 | Software developer | 30,000–75,000 | https://nationalcareers.service.gov.uk/job-profiles/software-developer |
| CAR04 | Data analyst (NCS: data analyst-statistician) | 28,000–65,000 | https://nationalcareers.service.gov.uk/job-profiles/data-analyst-statistician |
| CAR05 | Electrician | 26,000–45,000 | https://nationalcareers.service.gov.uk/job-profiles/electrician |
| CAR06 | Wind turbine technician | 25,000–47,000 | https://nationalcareers.service.gov.uk/job-profiles/wind-turbine-technician |
| CAR07 | Heat pump engineer | 24,000–46,000 | https://nationalcareers.service.gov.uk/job-profiles/heat-pump-engineer |
| CAR08 | Welder | 25,000–45,000 | https://nationalcareers.service.gov.uk/job-profiles/welder |
| CAR09 | Maintenance fitter | 24,000–38,000 | https://nationalcareers.service.gov.uk/job-profiles/maintenance-fitter |
| CAR10 | Large goods vehicle driver | 27,000–47,000 | https://nationalcareers.service.gov.uk/job-profiles/large-goods-vehicle-driver |

Skill notes:
- "Medication support" (CAR02) comes from the care worker profile's day-to-day tasks: "make sure medication is taken if needed".
- "Health and safety" (CAR05, CAR08, CAR09): the electrician profile asks you to "use equipment safely", and the welder and maintenance fitter profiles say many jobs need a CCNSG safety passport.
- "Digital skills" stands for "carry out basic tasks on a computer" or "use a computer and the main software packages".
- "Driving large vehicles" (CAR10): the profile says an HGV Skills Bootcamp means you "can drive large vehicles".
- No route has an unpaid placement on its profile, so no route says "unpaid".

## North East demand (ne_demand)

Source: North East Local Skills Improvement Plan (NELSIP) 2026–2029, North East Automotive Alliance (the designated Employer Representative Body), PDF:
https://northeastautomotivealliance.com/wp-content/uploads/2026/09/NEAA_NELSIP-2026-2029-Report_A4-36pp-FINAL.pdf
(linked from https://northeastautomotivealliance.com/neaa-projects/nelsip/).

In its occupation tables, "Historic" is the average 2021–25 monthly job postings and "Forecast" is the forecast monthly postings by 2029 (page 14).

Rule used: **high** = named as a high-volume, hard-to-fill entry-level role (page 9) or a priority occupation with forecast growth. **Medium** = a priority occupation or skills focus with a weaker or uncertain signal. **Low** = not named as a NELSIP priority sector or occupation.

| ID | Rating | Evidence (page of the PDF) |
| --- | --- | --- |
| CAR01 Healthcare assistant | high | p9: "intense competitive demand to fill high-volume, entry-level roles", listing "Social Care: Care Workers and Band 2 healthcare support assistants". |
| CAR02 Care worker | high | p9 (same list); p11: Care Workers/Home Carers (SOC 6135) is an Adult Social Care priority occupation; p23 table: 36.4 historic, 26 forecast. |
| CAR03 Software developer | high | p10–11: Programmers and software development professionals (SOC 2134) is a priority occupation in five of the eight NELSIP sectors; p22 Tech, Digital & AI table: 171.5 historic → 381.8 forecast. |
| CAR04 Data analyst | medium | p11: Data analysts (SOC 3544) is a Tech, Digital & AI priority occupation, and p9 lists "Data technicians" among entry-level roles in demand, but the p22 table forecasts fewer postings (115.6 historic → 57.2 forecast). |
| CAR05 Electrician | high | p9: "Construction: Plumbers, electricians, and retrofit installer assistants"; p20 Offshore Wind table: Electricians and electrical fitters (SOC 5241) 41.7 → 87.3. |
| CAR06 Wind turbine technician | high | p9: "Offshore Wind and Renewable energy: Wind turbine technicians and entry-level Installation engineers". |
| CAR07 Heat pump engineer | medium | p11: the Construction skills focus is "Retrofit & Heat Pumps: A rapid pivot from gas boiler skills to low-carbon retrofit and heat pump installation"; p9 lists retrofit installer assistants. But p7 says "Forecasting the timing and scale of market demand for new green technologies, such as heat pumps … is difficult", and p24: plumbers and heating installers (SOC 5315) 14.3 → 15. |
| CAR08 Welder | medium | p15 Advanced Manufacturing table: Welding trades (SOC 5213) 7.1 → 21.3, growing from a small base; not in the p9 entry-level list. |
| CAR09 Maintenance fitter | high | p9: "Advanced Manufacturing: Production operatives and entry-level maintenance technicians"; p20: Engineering technicians (SOC 3113) 38.3 → 87.8, "machining and equipment maintenance". |
| CAR10 Large goods vehicle driver | low | Transport and logistics is not one of the eight NELSIP sectors (p10–11), and no driving occupation is listed. Logistics appears only in passing (for example p20: "Severe talent deficits affect onshore logistics"). This rating reflects this one source only. |

## Courses (courses.csv)

Every course's `source_url` is its NCS "Find a course" details page. Title, provider, cost, entry requirements, format and venue town come from that page. The duration comes from the same course's NCS search-results listing (search near Newcastle upon Tyne).

- **Units:** a "year" counts as 52 weeks, a "month" as 4.33 weeks and a "day" as 1/7 of a week, rounded to 1 decimal place.
- **cost_gbp** is what an eligible learner pays.
  - Courses listed as "Free Courses for Jobs" (CRS09, CRS12–CRS15) show a full fee on NCS. They are 0 here, because GOV.UK says eligible learners (19 or over, earning below £25,750 or unemployed) "will not have to pay for your qualification" for a level 3, or a level 2 in construction, engineering or manufacturing: https://www.gov.uk/guidance/free-courses-for-jobs (fetched 4 November 2026). Their entry_requirements state this eligibility.
- **funded** is "yes" only where a fetched page says the course is funded or free for eligible learners: "fully funded", "free tuition", "Free Courses for Jobs" or "funded by the government". A £0 course whose page doesn't mention funding has funded "no" (it still counts as free through cost_gbp = 0).

| ID | Course | Provider | Cost (eligible learner) | Funded | Weeks | Source facts |
| --- | --- | --- | --- | --- | --- | --- |
| CRS01 | GCSE Maths | Gateshead College | 0 | yes | 52 (1 year, part-time evening) | "£0.00"; "Free to those aged 16-18 or adults without a grade C/4"; teaches solving problems with maths, logic and reasoning. |
| CRS02 | Functional Skills in English Level 1 | Gateshead College | 0 | yes | 26 (6 months) | "Most learners will qualify for free tuition"; reading, writing, speaking and listening. |
| CRS03 | Certificate in Data, Data Technician (Level 3) | Back to Work Training Limited | 0 | yes | 2.7 (19 days) | "100% online and fully funded"; "source, process, analyse and store data", "data-handling and IT skills". |
| CRS04 | Certificate in AI Programming with Python (Level 3) | Back to Work Training Limited | 0 | yes | 1.9 (13 days) | "fully funded"; "python scripting and programming libraries, as well as calculus essentials". |
| CRS05 | Certificate in Principles of Customer Service (Level 2) | Stockton-on-Tees Borough Council | 0 | no | 26 (6 months) | "£0.00"; aged 19+, lived in the UK 3+ years. |
| CRS06 | Certificate in Team Leading Principles (Level 2) | QDOS Training Limited | 0 | no | 4.3 (1 month) | "£0.00"; units on team leading and "Communicating Information and Knowledge in the Workplace". Mapped to Teamwork and Communication. |
| CRS07 | Certificate in Preparing to Work in Adult Social Care (Level 2) | North Tyneside Council | 0 | no | 16 | "£0.00"; online. Mapped to Caring for people. |
| CRS08 | Certificate in Understanding the Safe Handling of Medication in Health and Social Care (Level 2) | North Tyneside Council | 0 | no | 9 | "£0.00"; online. Mapped to Medication support. |
| CRS09 | Level 2 Diploma in Electrical Installations | Gateshead College | 0 | yes | 52 (1 year, full-time) | Free Courses for Jobs; units include health and safety, electrical circuits and installing wiring systems; for the building services industry; Skills Academy for Construction, Gateshead. |
| CRS10 | HGV Skills Bootcamp (Pathway D) | South Tyneside Council | 0 | yes | 16 | "Free - funded by the government if you are applying as an independent learner"; eligibility from the page; the car licence requirement comes from the NCS HGV driver profile; venue in North Shields. |
| CRS11 | Award in Welding Skills (Level 2) | Newcastle College (NCG) | 180 | no | 104 (2 years, part-time) | "£180.00", the maximum first-year cost; a reduction may be possible; Energy Academy, Wallsend. |
| CRS12 | Diploma in Engineering: Fabrication and Welding (Level 3) | Tyne Coast College | 0 | yes | 52 | Free Courses for Jobs (listed at £1,440); Tyne Metropolitan College, Wallsend. |
| CRS13 | Level 3 Diploma in Engineering (Wind Turbine) Maintenance, Installation and Commissioning | Newcastle College (NCG) | 0 | yes | 52 | Free Courses for Jobs (listed at £4,608); Energy Academy, Wallsend. |
| CRS14 | Level 2 Diploma in Engineering Operations | Newcastle College (NCG) | 0 | yes | 52 | Free Courses for Jobs (listed at £1,410); Rye Hill Campus, Newcastle upon Tyne. |
| CRS15 | Level 2 Diploma in Plumbing Studies | Tyne Coast College | 0 | yes | 52 | Free Courses for Jobs (listed at £1,287); Tyne Metropolitan College, Wallsend. |

The CRS05 (Stockton), CRS06 (QDOS) and CRS03/CRS04 (Back to Work Training) providers are not based in Tyne and Wear, but those courses are online.

## Shared skills list (20)

Caring for people; Communication; Construction knowledge; Customer service; Data analysis; Digital skills; Driving large vehicles; Electrical installation; Engineering knowledge; Fabrication; Health and safety; Maths; Medication support; Plumbing and heating; Problem solving; Programming; Teamwork; Using tools and equipment; Welding; Wind turbine maintenance.

Every career skill is taught by at least one course, and every course skill belongs to at least one career.

## Sources tried but not used

- OpenLearn (www.open.edu) refused automated requests (HTTP 403), so it has no courses here.
- The GOV.UK Skills Bootcamps finder URLs tried returned 404 or redirected. The HGV bootcamp (CRS10) comes from its NCS course listing instead.
