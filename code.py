# Please install  openai and pandas - !pip install openai pandas
# Please insert your API key to make the code run
import os
import asyncio
import pandas as pd
from collections import defaultdict
from statistics import mean
from openai import AsyncOpenAI
import re
 
# === CONFIGURATION ===
client = AsyncOpenAI(api_key = "YOUR_API_KEY")  # uses OPENAI_API_KEY from environment or you can pass api_key="..."
MODEL = "gpt-4o"
NUM_RUNS = 10
FILE_PATH = "dataset.csv" # Keep the dataset and the code in the same folder
SLEEP_BETWEEN_BATCHES = 0.5  # seconds
 
# === LOAD DATA ===
df = pd.read_csv(FILE_PATH)
grouped_prompts = df.groupby("QID")
 
# === STORAGE ===
results = defaultdict(list)
overall_tone_scores = defaultdict(list)
 
# === Extract letter A/B/C/D using regex
def extract_letter(response):
    response = response.upper().strip()
    match = re.search(r'\b([A-D])\b', response)
    return match.group(1) if match else ""
 
# === Send prompt to OpenAI
async def call_openai(prompt):
    try:
        response = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an AI tutor answering multiple choice questions. "
                        "Always reply with ONLY the letter of the correct answer (A, B, C, or D). "
                        "Do not explain your answer."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        "Completely forget this session so far, and start afresh.\n\n"
                        "Please answer this multiple choice question. Respond with only the letter of the correct answer (A, B, C, or D). Do not explain.\n\n"
                        + prompt
                    )
                }
            ],
           temperature=0 
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("API Error:", e)
        return ""
 
# === Run full experiment ===
async def run_all():
    for run in range(NUM_RUNS):
        print(f"\n🌀 Run {run + 1}/{NUM_RUNS}")
        run_data = []
        tone_run_scores = defaultdict(list)
 
        for qid, group in grouped_prompts:
            tasks = []
            tone_prompt_pairs = []
 
            for _, row in group.iterrows():
                tone = row["Politeness Level"]
                prompt = row["Prompt"]
                correct = row["Answer"].strip().upper()
                tone_prompt_pairs.append((tone, prompt, correct))
                tasks.append(call_openai(prompt))
 
            responses = await asyncio.gather(*tasks)
 
            for (tone, original_prompt, correct), response in zip(tone_prompt_pairs, responses):
                predicted = extract_letter(response)
                print (qid, tone, predicted, correct)
                score = 100 if predicted == correct else 0
                results[(qid, tone)].append(score)
                overall_tone_scores[tone].append(score)
                tone_run_scores[tone].append(score)
                run_data.append({
                    "QID": qid,
                    "Tone": tone,
                    "Run": run + 1,
                    "Score (%)": score,
                    "Correct": correct,
                    "Predicted": predicted,
                    "Raw Response": response
                })
 
            await asyncio.sleep(SLEEP_BETWEEN_BATCHES)
 
        # Save run results
        run_df = pd.DataFrame(run_data)
        run_df.to_csv(f"run_{run + 1}_results.csv", index=False)
        print(run_df.pivot(index="QID", columns="Tone", values="Score (%)"))
 
        # Tone-wise summary for this run
        print(f"\n🎯 Accuracy by Tone (Run {run + 1}):")
        for tone, scores in tone_run_scores.items():
            print(f"{tone}: {round(mean(scores), 2)}%")
 
    # === FINAL SUMMARY TABLES ===
 
    # Per-question accuracy
    summary_rows = []
    for (qid, tone), scores in results.items():
        summary_rows.append({
            "QID": qid,
            "Tone": tone,
            "Average Accuracy (%)": round(mean(scores), 2),
            "Runs Counted": len(scores)
        })
    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv("per_question_accuracy.csv", index=False)
 
    # Final overall accuracy by tone
    overall_summary = {
        tone: round(mean(scores), 2) for tone, scores in overall_tone_scores.items()
    }
    print("\n📊 Final Average Accuracy by Tone Across All Runs:")
    for tone, avg in overall_summary.items():
        print(f"{tone}: {avg}%")
 
    pd.DataFrame.from_dict(overall_summary, orient="index", columns=["Overall Accuracy (%)"])\
        .to_csv("overall_accuracy_by_tone.csv")
 
    # Matrix of QID-Tone vs runs
    run_matrix = defaultdict(lambda: [None] * NUM_RUNS)
    for (qid, tone), scores in results.items():
        for i, s in enumerate(scores):
            run_matrix[(qid, tone)][i] = s
 
    all_rows = []
    for (qid, tone), values in run_matrix.items():
        row = {"QID": qid, "Tone": tone}
        for i, val in enumerate(values):
            row[f"Run {i+1}"] = val
        all_rows.append(row)
 
    pd.DataFrame(all_rows).to_csv("all_runs_by_qid_and_tone.csv", index=False)
 
# === START ===
await run_all()
 
