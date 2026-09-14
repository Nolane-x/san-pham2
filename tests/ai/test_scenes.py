from nolane_studio.ai.scenes import split_script_into_scenes


def test_blank_script_returns_no_scenes():
    assert split_script_into_scenes("   ") == []


def test_sentence_grouping_is_deterministic_and_respects_soft_word_window():
    text = (
        "Một buổi sáng thành phố thức dậy trong ánh nắng nhẹ và mọi người bắt đầu công việc của mình. "
        "Trên con phố nhỏ một cửa hàng cà phê mở cửa và đón những vị khách đầu tiên. "
        "Bên trong người chủ kiểm tra đơn hàng rồi chuẩn bị từng ly cà phê thật cẩn thận. "
        "Đến trưa lượng khách tăng lên nhưng quy trình vẫn diễn ra đều đặn và nhanh chóng."
    )
    a = split_script_into_scenes(text, min_words=20, max_words=35)
    b = split_script_into_scenes(text, min_words=20, max_words=35)
    assert a == b
    assert len(a) >= 2
    assert [s.index for s in a] == list(range(len(a)))
    assert all(s.text for s in a)


def test_single_long_sentence_is_split_without_losing_words():
    words = [f"w{i}" for i in range(83)]
    scenes = split_script_into_scenes(" ".join(words), min_words=20, max_words=30)
    reconstructed = " ".join(scene.text for scene in scenes).split()
    assert reconstructed == words
    assert max(len(scene.text.split()) for scene in scenes) <= 30
