# pyright: basic
"""Phrase parts for TRL-Bench v3.1. Every part belongs to exactly one split.

Train, dev and calibration parts are authored here. Test parts come from
`data/bench/v31/sealed/test-parts.json`, written by `experiments.bench_v31.external` from a model
of another family, so the people who maintain the system do not choose the test wording.
Positive predicates avoid the hedge and negation words the evidence gate blocks. The singular
and plural forms are kept together so a sentence about two stops uses the plural verb and the
quoted phrase is the phrase in the sentence.
"""

import json
from pathlib import Path

SEALED = Path("data/bench/v31/sealed/test-parts.json")

# (id, split, singular, plural). English plurals differ; Turkish forms are the same.
CLOSED = {
    "en": [
        ("en-cl-1", "train", "is closed", "are closed"),
        ("en-cl-2", "train", "has been closed", "have been closed"),
        ("en-cl-3", "train", "is shut", "are shut"),
        ("en-cl-4", "train", "is shut down", "are shut down"),
        ("en-cl-5", "train", "has been shut", "have been shut"),
        ("en-cl-6", "train", "is out of service", "are out of service"),
        ("en-cl-7", "train", "has been taken out of service", "have been taken out of service"),
        ("en-cl-8", "train", "is temporarily closed", "are temporarily closed"),
        ("en-cl-9", "train", "is closed to the public", "are closed to the public"),
        ("en-cl-10", "train", "is closed for maintenance", "are closed for maintenance"),
        ("en-cl-11", "train", "is blocked off", "are blocked off"),
        ("en-cl-12", "train", "is sealed off", "are sealed off"),
        ("en-cl-13", "train", "is inaccessible", "are inaccessible"),
        ("en-cl-14", "train", "is offline", "are offline"),
        ("en-cl-15", "train", "has stopped operating", "have stopped operating"),
        ("en-cl-16", "train", "is withdrawn from service", "are withdrawn from service"),
        ("en-cl-17", "train", "is suspended", "are suspended"),
        ("en-cl-18", "train", "is off limits to passengers", "are off limits to passengers"),
        ("en-cl-19", "dev", "remains closed", "remain closed"),
        ("en-cl-20", "dev", "is currently shut", "are currently shut"),
        ("en-cl-21", "dev", "has gone out of service", "have gone out of service"),
        ("en-cl-22", "dev", "is taken out of operation", "are taken out of operation"),
        ("en-cl-23", "dev", "stays shut", "stay shut"),
        ("en-cl-24", "dev", "is barred to passengers", "are barred to passengers"),
        ("en-cl-25", "dev", "is fenced off", "are fenced off"),
        ("en-cl-26", "dev", "is closed down", "are closed down"),
        ("en-cl-27", "calibration", "will be closed", "will be closed"),
        ("en-cl-28", "calibration", "is closed off", "are closed off"),
        ("en-cl-29", "calibration", "is placed out of use", "are placed out of use"),
        ("en-cl-30", "calibration", "is locked up", "are locked up"),
        ("en-cl-31", "calibration", "has been put out of action", "have been put out of action"),
        ("en-cl-32", "calibration", "is held shut", "are held shut"),
    ],
    "tr": [
        ("tr-cl-1", "train", "kapalıdır", "kapalıdır"),
        ("tr-cl-2", "train", "kapatılmıştır", "kapatılmıştır"),
        ("tr-cl-3", "train", "kapalı tutulmaktadır", "kapalı tutulmaktadır"),
        ("tr-cl-4", "train", "geçici olarak kapalıdır", "geçici olarak kapalıdır"),
        ("tr-cl-5", "train", "kullanıma kapatılmıştır", "kullanıma kapatılmıştır"),
        ("tr-cl-6", "train", "hizmet dışı bırakılmıştır", "hizmet dışı bırakılmıştır"),
        ("tr-cl-7", "train", "hizmet vermemektedir", "hizmet vermemektedir"),
        ("tr-cl-8", "train", "hizmet verememektedir", "hizmet verememektedir"),
        ("tr-cl-9", "train", "trafiğe kapatılmıştır", "trafiğe kapatılmıştır"),
        ("tr-cl-10", "train", "yolcu girişine kapalıdır", "yolcu girişine kapalıdır"),
        ("tr-cl-11", "train", "erişime kapatılmıştır", "erişime kapatılmıştır"),
        ("tr-cl-12", "train", "durdurulmuştur", "durdurulmuştur"),
        ("tr-cl-13", "train", "faaliyet göstermemektedir", "faaliyet göstermemektedir"),
        ("tr-cl-14", "train", "hizmet dışıdır", "hizmet dışıdır"),
        ("tr-cl-15", "train", "yolcu alımına durdurulmuştur", "yolcu alımına durdurulmuştur"),
        ("tr-cl-16", "train", "hizmet vermeyecektir", "hizmet vermeyecektir"),
        ("tr-cl-17", "dev", "kapalı olacaktır", "kapalı olacaktır"),
        ("tr-cl-18", "dev", "kapalı kalacaktır", "kapalı kalacaktır"),
        ("tr-cl-19", "dev", "hizmet dışı kalmıştır", "hizmet dışı kalmıştır"),
        ("tr-cl-20", "dev", "seferlere kapatılmıştır", "seferlere kapatılmıştır"),
        ("tr-cl-21", "dev", "kullanım dışıdır", "kullanım dışıdır"),
        ("tr-cl-22", "dev", "yolcuya kapalıdır", "yolcuya kapalıdır"),
        ("tr-cl-23", "dev", "geçici süreyle kapalıdır", "geçici süreyle kapalıdır"),
        ("tr-cl-24", "dev", "işletim dışıdır", "işletim dışıdır"),
        ("tr-cl-25", "calibration", "kapatıldı", "kapatıldı"),
        ("tr-cl-26", "calibration", "kapalı durumdadır", "kapalı durumdadır"),
        ("tr-cl-27", "calibration", "hizmet veremeyecektir", "hizmet veremeyecektir"),
        ("tr-cl-28", "calibration", "kullanılamamaktadır", "kullanılamamaktadır"),
        ("tr-cl-29", "calibration", "faaliyet dışıdır", "faaliyet dışıdır"),
        ("tr-cl-30", "calibration", "kapalı tutulacaktır", "kapalı tutulacaktır"),
    ],
}  # fmt: skip
LEADS = {
    "en": [
        ("en-ld-1", "train", ""), ("en-ld-2", "train", "Notice: "), ("en-ld-3", "train", "Alert: "),
        ("en-ld-4", "train", "Attention: "), ("en-ld-5", "train", "Rider information: "),
        ("en-ld-6", "train", "Service update. "),
        ("en-ld-7", "dev", "Update: "), ("en-ld-8", "dev", "Attention riders. "),
        ("en-ld-9", "dev", "Heads up: "),
        ("en-ld-10", "calibration", "Service alert: "), ("en-ld-11", "calibration", "Reminder: "),
        ("en-ld-12", "calibration", "Latest: "),
    ],
    "tr": [
        ("tr-ld-1", "train", ""), ("tr-ld-2", "train", "Duyuru: "), ("tr-ld-3", "train", "Dikkat: "),
        ("tr-ld-4", "train", "Yolcu bilgilendirmesi: "), ("tr-ld-5", "train", "Hizmet güncellemesi: "),
        ("tr-ld-6", "dev", "Bilgi: "), ("tr-ld-7", "dev", "Sayın yolcularımız, "),
        ("tr-ld-8", "dev", "Önemli: "),
        ("tr-ld-9", "calibration", "Uyarı: "), ("tr-ld-10", "calibration", "Hatırlatma: "),
        ("tr-ld-11", "calibration", "Son durum: "),
    ],
}  # fmt: skip
TIME_FORMS = {
    "en": [
        ("en-tm-1", "train", "from {a} to {b}"), ("en-tm-2", "train", "between {a} and {b}"),
        ("en-tm-3", "train", "{a} to {b}"), ("en-tm-4", "train", "from {a} until {b}"),
        ("en-tm-5", "dev", "{a}-{b}"), ("en-tm-6", "dev", "starting {a} until {b}"),
        ("en-tm-7", "dev", "from {a} till {b}"),
        ("en-tm-8", "calibration", "{a} – {b}"), ("en-tm-9", "calibration", "from {a} up to {b}"),
        ("en-tm-10", "test", "until {b}, from {a}"), ("en-tm-11", "test", "from {a} through {b}"),
        ("en-tm-12", "test", "for the period {a} to {b}"), ("en-tm-13", "test", "during {a}–{b}"),
    ],
    "tr": [
        ("tr-tm-1", "train", "{a} ile {b} arasında"), ("tr-tm-2", "train", "{a}-{b} arası"),
        ("tr-tm-3", "train", "{a} ve {b} arasında"), ("tr-tm-4", "train", "{a} - {b} saatleri arasında"),
        ("tr-tm-5", "dev", "saat {a} ile {b} arasında"), ("tr-tm-6", "dev", "{a} ile {b} saatleri arasında"),
        ("tr-tm-7", "dev", "{a_abl} {b_dat} kadar"),
        ("tr-tm-8", "calibration", "{a} – {b} arası"), ("tr-tm-9", "calibration", "{a_abl} {b_dat} dek"),
        ("tr-tm-10", "test", "{b_dat} kadar, {a_abl} itibaren"), ("tr-tm-11", "test", "{a_abl} {b_dat} değin"),
        ("tr-tm-12", "test", "{a}–{b} saatleri boyunca"), ("tr-tm-13", "test", "{a_abl} başlayıp {b_dat} kadar"),
    ],
}  # fmt: skip
# Constructions that place the predicate relative to the subject and the time.
FRAMES = [
    ("fr-1", "train", "{lead}{S} {P} {T}."), ("fr-2", "train", "{lead}{T}, {S} {P}."),
    ("fr-3", "dev", "{lead}{S} {T} {P}."), ("fr-4", "dev", "{lead}{S} {P}, {T}."),
    ("fr-5", "calibration", "{lead}{S}, {T}, {P}."),
    ("fr-6", "test", "{lead}{S} - {P} {T}."), ("fr-7", "test", "{lead}{T} — {S} {P}."),
]  # fmt: skip
# One-sided closures. `{b}` gives the end, `{a}` the start. These forms are not under test, so
# splits may share their wording. Each split still owns its own ids.
UNTIL = {
    "en": [("en-un-1", "train", "until {b}"), ("en-un-2", "train", "up to {b}"),
           ("en-un-3", "dev", "till {b}"), ("en-un-4", "calibration", "until {b}"),
           ("en-un-5", "test", "until {b}"), ("en-un-6", "test", "up to {b}")],
    "tr": [("tr-un-1", "train", "{b_dat} kadar"), ("tr-un-2", "train", "{b_dat} dek"),
           ("tr-un-3", "dev", "saat {b_dat} kadar"), ("tr-un-4", "calibration", "{b_dat} dek"),
           ("tr-un-5", "test", "{b_dat} kadar"), ("tr-un-6", "test", "{b_dat} dek")],
}  # fmt: skip
FROM = {
    "en": [("en-fr-1", "train", "from {a}"), ("en-fr-2", "train", "since {a}"),
           ("en-fr-3", "dev", "starting {a}"), ("en-fr-4", "dev", "as of {a}"),
           ("en-fr-5", "calibration", "from {a}"),
           ("en-fr-6", "test", "from {a}"), ("en-fr-7", "test", "since {a}")],
    "tr": [("tr-fr-1", "train", "{a_abl} itibaren"), ("tr-fr-2", "train", "{a_abl} beri"),
           ("tr-fr-3", "dev", "saat {a_abl} itibaren"), ("tr-fr-4", "calibration", "{a_abl} itibaren"),
           ("tr-fr-5", "test", "{a_abl} itibaren"), ("tr-fr-6", "test", "{a_abl} beri")],
}  # fmt: skip
NEGATED = {
    "en": [("en-ng-1", "train", "is not closed"), ("en-ng-2", "train", "has not been closed"),
           ("en-ng-3", "dev", "is not shut"), ("en-ng-4", "dev", "is not closed to riders"),
           ("en-ng-5", "calibration", "is not out of service"), ("en-ng-6", "calibration", "has not been closed off")],
    "tr": [("tr-ng-1", "train", "kapalı değildir"), ("tr-ng-2", "train", "kapalı değilmiş"),
           ("tr-ng-3", "dev", "kapalı değil"), ("tr-ng-4", "dev", "hizmet dışı değildir"),
           ("tr-ng-5", "calibration", "kapatılmadı"), ("tr-ng-6", "calibration", "kapatılması söz konusu değildir")],
}  # fmt: skip
HEDGED = {
    "en": [("en-hd-1", "train", "might be closed"), ("en-hd-2", "train", "is possibly closed"),
           ("en-hd-3", "dev", "is expected to be closed"), ("en-hd-4", "dev", "is maybe closed"),
           ("en-hd-5", "calibration", "might possibly be shut"), ("en-hd-6", "calibration", "might be out of service")],
    "tr": [("tr-hd-1", "train", "kapalı olabilir"), ("tr-hd-2", "train", "belki kapalıdır"),
           ("tr-hd-3", "dev", "kapatılması bekleniyor"), ("tr-hd-4", "dev", "muhtemelen kapalıdır"),
           ("tr-hd-5", "calibration", "belki kapatılacaktır"), ("tr-hd-6", "calibration", "kapalı olması muhtemeldir")],
}  # fmt: skip
CALM = {
    "en": [("en-cm-1", "train", "Services are running normally today."),
           ("en-cm-2", "train", "All lines are on time."),
           ("en-cm-3", "train", "Normal service is in operation across the network."),
           ("en-cm-4", "dev", "All lines are operating as scheduled."),
           ("en-cm-5", "dev", "Trains and trams are running every few minutes."),
           ("en-cm-6", "calibration", "No changes to today's timetable."),
           ("en-cm-7", "calibration", "Today's timetable is unchanged.")],
    "tr": [("tr-cm-1", "train", "Seferler bugün normal seyrinde devam etmektedir."),
           ("tr-cm-2", "train", "Tüm hatlar zamanında çalışmaktadır."),
           ("tr-cm-3", "train", "Ağ genelinde normal servis sürmektedir."),
           ("tr-cm-4", "dev", "Tüm hatlarda seferler tarifesine uygundur."),
           ("tr-cm-5", "dev", "Metro ve tramvay birkaç dakikada bir çalışmaktadır."),
           ("tr-cm-6", "calibration", "Bugünkü tarifede bir değişiklik yoktur."),
           ("tr-cm-7", "calibration", "Bugünkü sefer planı değişmemiştir.")],
}  # fmt: skip
NOTES = {
    "en": [("en-nt-1", "train", "(no lifts)"), ("en-nt-2", "train", "(no escalators)"),
           ("en-nt-3", "train", "No bicycles are allowed."),
           ("en-nt-4", "dev", "No parking is available."), ("en-nt-5", "dev", "(no toilets)"),
           ("en-nt-6", "calibration", "(no ramp)"), ("en-nt-7", "calibration", "(no shelter)")],
    "tr": [("tr-nt-1", "train", "(asansör yok)"), ("tr-nt-2", "train", "(yürüyen merdiven yok)"),
           ("tr-nt-3", "train", "Bisiklet kabul edilmemektedir."),
           ("tr-nt-4", "dev", "Otopark mevcut değildir."), ("tr-nt-5", "dev", "(tuvalet yok)"),
           ("tr-nt-6", "calibration", "(rampa yok)"), ("tr-nt-7", "calibration", "(sığınak yok)")],
}  # fmt: skip
DATES = {
    "en": [("en-dt-1", "train", "On {d}, "), ("en-dt-2", "dev", "Dated {d}: "),
           ("en-dt-3", "calibration", "For {d}, "), ("en-dt-4", "test", "Valid {d}: ")],
    "tr": [("tr-dt-1", "train", "{d} tarihinde "), ("tr-dt-2", "dev", "Tarih {d}: "),
           ("tr-dt-3", "calibration", "{d} günü için "), ("tr-dt-4", "test", "{d} tarihli bildirim: ")],
}  # fmt: skip

TABLES = (
    "CLOSED",
    "LEADS",
    "TIME_FORMS",
    "UNTIL",
    "FROM",
    "NEGATED",
    "HEDGED",
    "CALM",
    "NOTES",
    "DATES",
)


def sealed_parts() -> dict[str, dict[str, list[list[str]]]]:
    """Test-owned parts from the external model, or nothing when they are not generated yet."""
    return json.loads(SEALED.read_text(encoding="utf-8")) if SEALED.exists() else {}


def table(name: str, lang: str) -> list[tuple[str, ...]]:
    """The authored rows of one table plus the sealed test rows for that language."""
    rows = [tuple(item) for item in globals()[name][lang]]
    extra = sealed_parts().get(name, {}).get(lang, [])
    width = 4 if name == "CLOSED" else 3
    return rows + [tuple(item[:width]) for item in extra]


def globals_table(name: str, lang: str) -> list[tuple[str, ...]]:
    """Authored rows only, used to keep sealed parts distinct from them."""
    return [tuple(item) for item in globals()[name][lang]]
