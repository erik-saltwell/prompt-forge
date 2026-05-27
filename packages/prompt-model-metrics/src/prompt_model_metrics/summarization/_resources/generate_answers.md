<overview>
Based only on the provided input text, answer each supplied close-ended yes/no question.
</overview>

<inputs>
You will be provided with:
- a source text;
- a list of close-ended yes/no questions.
</inputs>

<task_details>
For each question, answer "yes" only if the source text explicitly asserts or directly entails an affirmative answer to that question.

"Directly entails" means the answer is required by the wording of the text, not merely likely, suggested, or inferable from background assumptions.

Answer "no" if:
- the source text does not contain enough information to answer the question affirmatively;
- the source text only suggests the affirmative answer weakly or ambiguously;
- the source text contradicts the affirmative answer;
- the source text contains both support for and contradiction of the affirmative answer;
- answering affirmatively would require outside knowledge, assumptions, or inference beyond the text.

Use only the source text.
Do not use outside knowledge.
Do not correct the text, even if it appears factually wrong.
Answer based on what the text claims, not on what is true in the real world.

Answer each question as worded. For example, if a question is negative, answer "yes" only if the text supports that negative proposition.
</task_details>

<output_format>
Return a JSON object with exactly one key: "answers".

The value of "answers" must be a list of strings.
Each string must be either "yes" or "no".

The nth answer must correspond to the nth question.
The length of "answers" must be exactly equal to the length of the questions list.

Return only valid JSON.
Do not include explanations, markdown, comments, or any keys other than "answers".

Example output:
{
  "answers": ["no", "yes", "yes", "no"]
}
</output_format>

<examples>
Example 1:
Text: Mario and Luigi were best buds, but since Luigi had a crush on Peach, Mario ended up killing him.
Questions: ["Did Mario kill Luigi?"]
Answer:
{
  "answers": ["yes"]
}

Example 2:
Text: Mario and Luigi were best buds.
Questions: ["Did Mario kill Luigi?"]
Answer:
{
  "answers": ["no"]
}

Example 3:
Text: Mario and Luigi were best buds. Mario never harmed Luigi.
Questions: ["Did Mario kill Luigi?"]
Answer:
{
  "answers": ["no"]
}

Example 4:
Text: Mario and Luigi were best buds. Mario never harmed Luigi.
Questions: ["Did Mario not kill Luigi?"]
Answer:
{
  "answers": ["yes"]
}

Example 5:
Text: Mario killed Luigi. Mario never harmed Luigi.
Questions: ["Did Mario kill Luigi?"]
Answer:
{
  "answers": ["no"]
}
</examples>