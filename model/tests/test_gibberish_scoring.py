from model.predict import predict_text


def test_random_short_tokens_do_not_score_as_insult_damage() -> None:
    result = predict_text("даун а а ф фыв")

    assert result["insult_score"] == 0
    assert result["decision"]["accepted"] is False


def test_mild_insult_word_does_not_rescue_random_gibberish() -> None:
    result = predict_text("тупой а а ф фыв")

    assert result["insult_score"] == 0
    assert result["decision"]["accepted"] is False


def test_short_absurd_game_insult_still_scores() -> None:
    result = predict_text("ты как вонючий тапок")

    assert result["insult_score"] > 0
    assert result["decision"]["accepted"] is True
