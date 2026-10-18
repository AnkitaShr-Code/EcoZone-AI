EcoZone AI. The explainer, version two. What we built, what we decided, and when.

Part one. Where we are right now.

It is the morning of the eighteenth of October, submission day. EcoZone AI is a working prototype, live on Google Cloud Run, with no login. It runs on a real part of Pune, Deccan Gymkhana and Fergusson College: sixty five blocks, six hundred twenty three buildings, thirty waiting points like bus stops and school gates.

Both modes work end to end on real data. In Repair, a planner sets a budget and gets a plan of trees, shade structures, depaving, pocket green and cool roofs, with a map of where each one goes. In Protect, a planner tests a proposed building on a vacant plot and sees a risk label, then three design options to compare.

Every number on screen comes from our own scoring engine, written in plain Python. Gemini proposes and explains. It never computes a score. That one rule shaped almost every decision you are about to hear.

Part two. What happened, and when.

October thirteenth to fifteenth. Design. We wrote the planning document, the deck plan and the task list. The first big decision was to make Repair the lead mode and Protect the second, because Repair has the clearer story: a ward office has a few lakh rupees and needs to know where to spend it. We also decided the app never approves or denies anything, and never shows temperatures or wind speeds. It reports prototype indices from zero to one hundred, for comparing options in the same area. On the fifteenth we decided that plain code, not an AI, routes each request. The interface never sends free chat, so an AI routing step would only add delay.

October sixteenth. The build began, and I took the role of orchestrator. The key decision was to split the work into packages that could run in parallel, around three agreed interfaces: the data bundle between the data pipeline and the engine, the engine's public functions, and the API contract between the server and the app. Because those three were fixed first, nobody waited for anybody. That day we merged the project skeleton with automatic checks, and the API contract, written once in Python and turned into types for the app. We also set default unit costs for each intervention from cited public sources. One honest note: none of those sources is specific to Pune. They are labelled planner input.

October seventeenth, early. The API routes, and the app connected to them. Then the agent layer, and here we made two decisions people ask about. First, we did not use Google's Agent Development Kit. We wrote a small loop in plain asyncio on the Gemini client instead, because we needed full control over the order of steps, a strict output check, and tests that run without a cloud call. Second, every test uses a fake model, so the whole search loop can be tested thousands of times for free and gives the same answer each time.

October seventeenth, daytime. Dhananjay's data pipeline merged, building the Deccan bundle from OpenStreetMap only. Earth Engine approval had not landed, so we built the version without it. In review we found two problems. A tree row was being judged on the average narrowness of its street, so a mostly open street with one tight stretch could pass. We changed it to judge the worst stretch. And a row could become a multi-part line that the server could not send. We fixed both. The area is real, but building heights are mostly a typology default, because OpenStreetMap rarely tags heights. The bundle counts that gap openly instead of hiding it.

That afternoon the service went to Cloud Run, and the bundle moved to Cloud Storage. The first deploy loaded no data, because the server could not read a cloud storage address. Ankita and I both wrote a fix at the same time. Hers merged first, and I closed mine and kept only its documentation fixes. Lesson: tell each other before starting.

October seventeenth, evening. Ankita's engine landed, and the evaluation suite we built around it found three real bugs. One: the greedy baseline could stop just under the quick-win share, which made its own plan invalid. Two: the Protect risk label measured the whole area, so a big drop in breeze on one block rounded to nothing and every option read low. We changed it to measure the parcel's own block. Three: a one or two storey building could look like it improved ventilation, which is backwards. We fixed all three, with tests, and the evals now pass. We also redefined waiting points covered. It used to count only shade structures, which the search almost never picks, so it read zero in most plans. Now it counts any waiting point with newly shaded footpath within thirty metres at three in the afternoon.

Speed was the other big change. The same engine took minutes for a plan. After caching the shadows that never change, rescoring takes tens of milliseconds and the greedy baseline takes seconds to tens of seconds.

Late that night, Gemini. Google was retiring the two point five models on the twentieth of October, so we chose the three point five and three point eight Flash models on the global endpoint. The first live search on Cloud Run timed out. The cause was that these models think before answering, which took up to a hundred seconds per proposal. Setting thinking to low brought a proposal to about twenty five seconds, and a whole search to about eighty. We also cut the search to two rounds, and changed the prompt so quick-win sites are always shown to the model, because it was being drowned in tree rows and could not meet the share.

October eighteenth, early morning. We ran the live evaluations. At a ten lakh budget Gemini beat the greedy baseline, narrowly. At fifty lakh and two crore it lost by about four to five points. A repeat run scored closer, so one run proves little. We are reporting exactly that, and nothing more. Then the Earth Engine heat check, run by Ankita. We compared our heat index with Landsat satellite surface temperature on the thirty three held out blocks. The rank correlation was plus zero point one nine, and not statistically significant. On all sixty five blocks it was plus zero point three, which is significant. So the index leans the right way, but we do not call it validated. We removed every claim that said it was checked against satellite, and every mention of the Agent Development Kit, from the README and the deck plan.

Part three. What each decision protects.

One engine scores everything. That protects trust: a planner can ask where any number came from, and the answer is always the same function.

The greedy baseline always runs beside Gemini. That protects honesty: if the simple method wins, the app says so. At the budgets we measured, it often does.

Quick wins are a setting, not an afterthought. That protects the summer: without it every plan was only trees, which take years.

Rejected options are shown with reasons. A dense tree row on a narrow street is rejected because it blocks the breeze.

Fail soft. If Gemini is slow or wrong, the planner still gets a plan from the engine, with a plain template in place of the AI's explanation.

Part four. What we chose not to do.

No saved plans or history. The server keeps run results only in memory, so a restart loses them. We decided that is a next step, not a prototype need, and the interface for a database is already in place. We also did not use satellite data for the scores themselves. Roof albedo from Sentinel-2 would change every number the night before submission, so it is future work.

Part five. What is left.

Make the repository public, after a secrets scan that found nothing. Choose the demo parcel from real output. Take the screenshots, build slides five to thirteen from them, record the three minute video, upload it, check the live link opens logged out, and submit.

That is the story: a design written in three days, a build run in parallel against agreed interfaces, bugs found by our own tests and fixed, and results reported as measured, including the ones that do not flatter us.
