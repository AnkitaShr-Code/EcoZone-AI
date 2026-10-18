EcoZone AI. The short version. What we built, and the decisions that shaped it.

It is the morning of the eighteenth of October. EcoZone AI is a live prototype on Google Cloud Run, running on a real part of Pune, Deccan Gymkhana. Repair turns a budget into a plan of trees, shade, depaving and cool roofs. Protect tests a proposed building and shows what it does to the breeze, heat, green and shade around it.

One rule shaped everything. Every number comes from our own engine. Gemini proposes and explains, and never computes a score.

Here is what happened, and when.

October thirteenth to fifteenth. We made Repair the lead mode. The app never approves or denies anything, and never shows temperatures. Plain code, not an AI, routes each request.

October sixteenth. We fixed three interfaces first: the data bundle, the engine, and the API contract. That let everyone build in parallel.

October seventeenth. We skipped Google's agent kit and wrote a small loop in plain code, so every step can be tested with a fake model. The evaluations then found three real engine bugs. The baseline plan could miss its quick-win share. The Protect risk label looked at the whole area, so it always read low. And a small building could look like it improved the breeze. We fixed all three. We also moved off the Gemini two point five models, which retire on the twentieth, and set thinking to low, which cut a search from about five minutes to about eighty seconds.

October eighteenth. The live Gemini tests were mixed. Gemini beat the simple baseline at a small budget and lost at larger ones, and we report exactly that. The satellite heat check agreed with our heat index only weakly on held out blocks, so we do not call the index validated. We removed every claim we could not back up.

We chose not to build saved plans, and not to add satellite data to the scores. Both are future work.

What is left: make the repository public, choose the demo parcel, record the video, finish the deck, and submit.
