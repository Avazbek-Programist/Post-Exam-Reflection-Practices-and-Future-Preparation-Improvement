from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime
from pathlib import Path

import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
SURVEY_FILE = BASE_DIR / "survey_questions.json"

DATE_FORMATS: tuple[str, ...] = ("%Y-%m-%d",)
ALLOWED_NAME_CHARACTERS: frozenset[str] = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz -'"
)


def load_survey_definition(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        survey_data: dict = json.load(file)

    question_count = len(survey_data.get("questions", []))
    if not 15 <= question_count <= 25:
        raise ValueError("The questionnaire must contain between 15 and 25 questions.")

    for question in survey_data.get("questions", []):
        option_count = len(question.get("options", []))
        if not 3 <= option_count <= 5:
            raise ValueError("Each question must contain between 3 and 5 answer options.")

    if not survey_data.get("title"):
        raise ValueError("The survey title is missing.")

    return survey_data


def validate_name(raw_name: str) -> str | None:
    cleaned_name = " ".join(raw_name.split())
    if not cleaned_name:
        return None

    if cleaned_name[0] in "-'" or cleaned_name[-1] in "-'":
        return None

    letter_count = 0
    previous_special = False

    for character in cleaned_name:
        if character not in ALLOWED_NAME_CHARACTERS:
            return None

        if character.isalpha():
            letter_count += 1
            previous_special = False
            continue

        if character in "-'":
            if previous_special:
                return None
            previous_special = True
        else:
            previous_special = False

    if letter_count == 0:
        return None

    return cleaned_name


def validate_date_of_birth(raw_date: str) -> str | None:
    today: date = date.today()

    for date_format in DATE_FORMATS:
        try:
            parsed_date = datetime.strptime(raw_date, date_format).date()
        except ValueError:
            continue

        age_years = (today - parsed_date).days // 365
        if parsed_date >= today or age_years > 120:
            return None
        return parsed_date.isoformat()

    return None


def validate_student_id(raw_student_id: str) -> str | None:
    student_id = raw_student_id.strip()
    if student_id.isdigit():
        return student_id
    return None


def interpret_score(total_score: int, result_bands: list[dict]) -> dict:
    for band in result_bands:
        if band["min_score"] <= total_score <= band["max_score"]:
            return band
    raise ValueError("The total score does not fit any interpretation range.")


def build_result_record(
    survey_data: dict,
    participant: dict,
    responses: list[dict],
    total_score: int,
    interpretation: dict,
) -> dict:
    max_score = sum(
        max(option["score"] for option in question["options"])
        for question in survey_data["questions"]
    )
    reflection_strength = round(((max_score - total_score) / max_score) * 100.0, 2)

    return {
        "survey_title": survey_data["title"],
        "participant_name": participant["full_name"],
        "date_of_birth": participant["date_of_birth"],
        "student_id": participant["student_id"],
        "question_count": len(survey_data["questions"]),
        "total_score": total_score,
        "max_score": max_score,
        "reflection_strength": reflection_strength,
        "interpretation_label": interpretation["label"],
        "interpretation_message": interpretation["message"],
        "completed_at": datetime.now().isoformat(timespec="seconds"),
        "responses": responses,
    }


def result_to_text(result_record: dict) -> str:
    lines = [
        f"Survey Title: {result_record['survey_title']}",
        f"Participant Name: {result_record['participant_name']}",
        f"Date of Birth: {result_record['date_of_birth']}",
        f"Student ID: {result_record['student_id']}",
        f"Question Count: {result_record['question_count']}",
        f"Total Score: {result_record['total_score']} / {result_record['max_score']}",
        f"Reflection Strength: {result_record['reflection_strength']}%",
        f"Interpretation: {result_record['interpretation_label']}",
        f"Guidance: {result_record['interpretation_message']}",
        f"Completed At: {result_record['completed_at']}",
        "Responses:",
    ]

    for response in result_record["responses"]:
        lines.append(f"{response['question_number']}. {response['question']}")
        lines.append(f"Answer: {response['selected_option']}")
        lines.append(f"Score: {response['score']}")

    return "\n".join(lines)


def result_to_csv(result_record: dict) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "survey_title",
            "participant_name",
            "date_of_birth",
            "student_id",
            "question_count",
            "total_score",
            "max_score",
            "reflection_strength",
            "interpretation_label",
            "interpretation_message",
            "completed_at",
            "responses_json",
        ],
    )
    writer.writeheader()
    writer.writerow(
        {
            "survey_title": result_record["survey_title"],
            "participant_name": result_record["participant_name"],
            "date_of_birth": result_record["date_of_birth"],
            "student_id": result_record["student_id"],
            "question_count": result_record["question_count"],
            "total_score": result_record["total_score"],
            "max_score": result_record["max_score"],
            "reflection_strength": result_record["reflection_strength"],
            "interpretation_label": result_record["interpretation_label"],
            "interpretation_message": result_record["interpretation_message"],
            "completed_at": result_record["completed_at"],
            "responses_json": json.dumps(result_record["responses"], ensure_ascii=False),
        }
    )
    return output.getvalue()


def sanitize_filename(text: str) -> str:
    safe_characters = []
    for character in text:
        if character.isalnum():
            safe_characters.append(character)
        elif character in {" ", "-", "_"}:
            safe_characters.append("_")
    return "".join(safe_characters).strip("_") or "result"


def render_download_buttons(result_record: dict) -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = sanitize_filename(result_record["participant_name"])

    st.download_button(
        "Download TXT result",
        data=result_to_text(result_record),
        file_name=f"reflection_survey_{safe_name}_{timestamp}.txt",
        mime="text/plain",
    )
    st.download_button(
        "Download CSV result",
        data=result_to_csv(result_record),
        file_name=f"reflection_survey_{safe_name}_{timestamp}.csv",
        mime="text/csv",
    )
    st.download_button(
        "Download JSON result",
        data=json.dumps(result_record, indent=2, ensure_ascii=False),
        file_name=f"reflection_survey_{safe_name}_{timestamp}.json",
        mime="application/json",
    )


def main() -> None:
    st.set_page_config(
        page_title="Post-Exam Reflection Survey",
        page_icon="📝",
        layout="centered",
    )

    st.title("Post-Exam Reflection Survey")

    try:
        survey_data = load_survey_definition(SURVEY_FILE)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as error:
        st.error(f"Unable to load the survey: {error}")
        st.stop()

    st.write(survey_data["description"])
    st.info(survey_data["questionnaire_notice"])

    with st.form("reflection_survey_form"):
        st.subheader("Participant details")
        full_name = st.text_input("Full name")
        date_of_birth = st.text_input("Date of birth (YYYY-MM-DD)")
        student_id = st.text_input("Student ID")

        st.subheader("Questions")
        selected_indices: list[int] = []

        for question_number, question_data in enumerate(survey_data["questions"], start=1):
            option_labels = [
                f"{option['text']} ({option['score']})"
                for option in question_data["options"]
            ]
            selection = st.radio(
                f"{question_number}. {question_data['prompt']}",
                options=range(len(option_labels)),
                format_func=lambda index, labels=option_labels: labels[index],
                index=None,
                key=f"question_{question_number}",
            )
            selected_indices.append(selection)

        submitted = st.form_submit_button("Submit survey")

    if not submitted:
        return

    name_error = validate_name(full_name)
    dob_error = validate_date_of_birth(date_of_birth)
    student_id_error = validate_student_id(student_id)

    if name_error is None:
        st.error("Enter a valid full name using letters, spaces, hyphens, or apostrophes only.")
        return
    if dob_error is None:
        st.error("Enter a valid date of birth in YYYY-MM-DD format.")
        return
    if student_id_error is None:
        st.error("Student ID must contain digits only.")
        return
    if any(selection is None for selection in selected_indices):
        st.error("Please answer every question before submitting.")
        return

    participant = {
        "full_name": name_error,
        "date_of_birth": dob_error,
        "student_id": student_id_error,
    }

    responses: list[dict] = []
    total_score = 0

    for question_number, question_data in enumerate(survey_data["questions"], start=1):
        selected_index = selected_indices[question_number - 1]
        selected_option = question_data["options"][selected_index]
        response = {
            "question_number": question_number,
            "question": question_data["prompt"],
            "selected_option": selected_option["text"],
            "score": int(selected_option["score"]),
        }
        responses.append(response)
        total_score += response["score"]

    interpretation = interpret_score(total_score, survey_data["results"])
    result_record = build_result_record(
        survey_data=survey_data,
        participant=participant,
        responses=responses,
        total_score=total_score,
        interpretation=interpretation,
    )

    st.success("Survey submitted successfully.")
    st.subheader("Result summary")
    st.write(f"**Participant:** {result_record['participant_name']}")
    st.write(f"**Score:** {result_record['total_score']} / {result_record['max_score']}")
    st.write(f"**Reflection strength:** {result_record['reflection_strength']}%")
    st.write(f"**Interpretation:** {result_record['interpretation_label']}")
    st.write(f"**Guidance:** {result_record['interpretation_message']}")

    with st.expander("Show all responses"):
        for response in result_record["responses"]:
            st.write(f"**{response['question_number']}. {response['question']}**")
            st.write(f"Answer: {response['selected_option']}")
            st.write(f"Score: {response['score']}")

    st.subheader("Download the result")
    render_download_buttons(result_record)


if __name__ == "__main__":
    main()
