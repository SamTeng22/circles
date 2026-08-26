from app.services.grading import grade_question


# --- multiple choice / true false (share the scalar-equality branch) --------

def test_multiple_choice_correct():
    q = {"question_type": "multiple_choice", "correct_answer": "A. x"}
    assert grade_question(q, "A. x") is True


def test_multiple_choice_incorrect():
    q = {"question_type": "multiple_choice", "correct_answer": "A. x"}
    assert grade_question(q, "B. y") is False


def test_true_false_correct():
    q = {"question_type": "true_false", "correct_answer": "True"}
    assert grade_question(q, "True") is True


def test_true_false_incorrect():
    q = {"question_type": "true_false", "correct_answer": "True"}
    assert grade_question(q, "False") is False


def test_missing_question_type_defaults_to_multiple_choice():
    q = {"correct_answer": "A. x"}  # pre-existing row, no question_type field
    assert grade_question(q, "A. x") is True
    assert grade_question(q, "B. y") is False


def test_unknown_question_type_fails_closed():
    q = {"question_type": "essay", "correct_answer": "A. x"}
    assert grade_question(q, "A. x") is False


# --- fill in the blank --------------------------------------------------------

def test_fill_in_blank_exact_match():
    q = {"question_type": "fill_in_blank", "accepted_answers": ["photosynthesis"]}
    assert grade_question(q, "photosynthesis") is True


def test_fill_in_blank_case_and_whitespace_insensitive():
    q = {"question_type": "fill_in_blank", "accepted_answers": ["photosynthesis"]}
    assert grade_question(q, "  Photosynthesis  ") is True


def test_fill_in_blank_matches_any_accepted_variant():
    q = {"question_type": "fill_in_blank", "accepted_answers": ["mitochondria", "mitochondrion"]}
    assert grade_question(q, "Mitochondrion") is True


def test_fill_in_blank_falls_back_to_correct_answer_when_no_accepted_answers():
    q = {"question_type": "fill_in_blank", "correct_answer": "photosynthesis"}
    assert grade_question(q, "photosynthesis") is True


def test_fill_in_blank_wrong_answer():
    q = {"question_type": "fill_in_blank", "accepted_answers": ["photosynthesis"]}
    assert grade_question(q, "respiration") is False


def test_fill_in_blank_rejects_non_string_submission():
    q = {"question_type": "fill_in_blank", "accepted_answers": ["photosynthesis"]}
    assert grade_question(q, {"a": "b"}) is False


# --- matching -----------------------------------------------------------------

def _matching_question():
    return {
        "question_type": "matching",
        "pairs": [
            {"left": "Mitochondria", "right": "Produces energy"},
            {"left": "Nucleus", "right": "Stores DNA"},
        ],
    }


def test_matching_all_correct():
    q = _matching_question()
    submitted = {"Mitochondria": "Produces energy", "Nucleus": "Stores DNA"}
    assert grade_question(q, submitted) is True


def test_matching_one_wrong_pair():
    q = _matching_question()
    submitted = {"Mitochondria": "Stores DNA", "Nucleus": "Produces energy"}
    assert grade_question(q, submitted) is False


def test_matching_missing_key_fails():
    q = _matching_question()
    submitted = {"Mitochondria": "Produces energy"}
    assert grade_question(q, submitted) is False


def test_matching_extra_key_fails():
    q = _matching_question()
    submitted = {
        "Mitochondria": "Produces energy",
        "Nucleus": "Stores DNA",
        "Ribosome": "Synthesizes proteins",
    }
    assert grade_question(q, submitted) is False


def test_matching_rejects_non_dict_submission():
    q = _matching_question()
    assert grade_question(q, "Produces energy") is False
