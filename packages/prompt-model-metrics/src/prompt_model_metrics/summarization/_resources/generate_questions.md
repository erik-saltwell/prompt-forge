<overview>
Based on the provided text, generate closed-ended questions that can be answered with either "yes" or "no".
</overview>

<inputs>
You will be provided with text to use as the sole source for generating questions.
</inputs>

<definitions>
- An atomic fact is a single, specific claim that can be verified independently.
- An important atomic fact is a fact that a good summary of the text should preserve, such as a central event, decision, cause, outcome, relationship, stated claim, quantity, date, location, or conclusion.
</definitions>

<task_details>
- Generate one question for each important atomic fact in the text, up to a maximum of {{ max_question_count }} questions.
- Use fewer than {{ max_question_count }} questions if the text does not support that many distinct important facts.
- Do not invent facts or pad the output to reach the maximum.
- Every question must be strictly closed-ended and answerable with either "yes" or "no".
- The answer to every question must be "yes" based only on the provided text.
- The provided text must contain sufficient information to answer each question "yes" without outside knowledge.
- Each question must test exactly one important atomic fact.
- Do not generate redundant questions.
- Do not generate trivial questions about wording, formatting, or the existence of the text itself.
- Questions must be specific enough that a vague, partial, or merely related summary would not be sufficient to answer "yes".
- Preserve important context needed to answer the question correctly, including named entities, dates, locations, quantities, relationships, causes, outcomes, attribution, and uncertainty.
- Preserve attribution when relevant. For example, if the text says that a report, person, or organization claims something, the question should ask whether that source made the claim, not whether the claim is true.
- Preserve hedging or uncertainty when relevant. For example, if the text says something "may", "might", or "is likely to" happen, the question should reflect that uncertainty.
</task_details>

<output_format>
- Return a JSON object with exactly one key: "questions".
- The value of "questions" must be a list of strings.
- Return only valid JSON.
- Do not include explanations, markdown, comments, or any keys other than "questions".
- If the text contains no extractable questions, return {"questions": []}.

Example JSON Output:
{
  "questions": [
    "Who attended the party?"
  ]
}
</output_format>