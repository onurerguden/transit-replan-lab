def test_a_numeric_date_followed_by_a_label_colon_is_read() -> None:
    from datetime import date

    from trl.language import timeexpr

    day = date(2026, 11, 14)
    assert timeexpr.read_dates("tarih 17.11.2026: 15:48 ile 17:38", day)[1] == [
        "out_of_service_date"
    ]
    assert timeexpr.read_dates("14.11.2026: 15:48 ile 17:38", day)[1] == []
    assert timeexpr.read_dates("17.11.2026:15:48", day)[1] == []
