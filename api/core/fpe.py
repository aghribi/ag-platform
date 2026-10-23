"""
Format-Preserving Entity replacement.

Given an original PII value and a deterministic seed (derived from HMAC of the
user key + original value), generates a realistic-looking fake replacement of
the same type and approximate format.  The same input always produces the same
output for a given key — making round-trips consistent.
"""
import hashlib
import hmac
import re
import struct

# ── Word lists ────────────────────────────────────────────────────────────────

_FIRST_NAMES = [
    "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael",
    "Linda", "William", "Barbara", "David", "Susan", "Richard", "Jessica",
    "Joseph", "Sarah", "Thomas", "Karen", "Charles", "Lisa", "Christopher",
    "Nancy", "Daniel", "Betty", "Matthew", "Margaret", "Anthony", "Sandra",
    "Mark", "Ashley", "Donald", "Dorothy", "Steven", "Kimberly", "Paul",
    "Emily", "Andrew", "Donna", "Kenneth", "Michelle", "Joshua", "Carol",
    "Kevin", "Amanda", "Brian", "Melissa", "George", "Deborah", "Timothy",
    "Stephanie", "Ronald", "Rebecca", "Edward", "Sharon", "Jason", "Laura",
    "Jeffrey", "Cynthia", "Ryan", "Kathleen", "Jacob", "Amy", "Gary",
    "Angela", "Nicholas", "Shirley", "Eric", "Anna", "Jonathan", "Brenda",
    "Stephen", "Pamela", "Larry", "Emma", "Justin", "Nicole", "Scott",
    "Helen", "Brandon", "Samantha", "Benjamin", "Katherine", "Samuel",
    "Christine", "Raymond", "Debra", "Gregory", "Rachel", "Frank", "Carolyn",
    "Alexander", "Janet", "Patrick", "Catherine", "Jack", "Maria", "Dennis",
    "Heather", "Jerry", "Diane",
]

_LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark",
    "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King",
    "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green",
    "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell",
    "Carter", "Roberts", "Turner", "Phillips", "Evans", "Collins", "Stewart",
    "Morris", "Morales", "Murphy", "Cook", "Rogers", "Gutierrez", "Ortiz",
    "Morgan", "Cooper", "Peterson", "Bailey", "Reed", "Kelly", "Howard",
    "Ramos", "Kim", "Cox", "Ward", "Richardson", "Watson", "Brooks",
    "Chavez", "Wood", "James", "Bennett", "Gray", "Mendoza", "Ruiz",
    "Hughes", "Price", "Alvarez", "Castillo", "Sanders", "Patel", "Myers",
    "Long", "Ross", "Foster", "Jimenez", "Powell", "Jenkins", "Perry",
    "Russell", "Sullivan", "Bell", "Coleman",
]

_EMAIL_DOMAINS = [
    "mailbox.net", "webmail.org", "fastmail.io", "inboxhub.com",
    "mailzone.net", "quickmail.org", "netpost.io", "emailhub.com",
    "protonbox.net", "clearmail.org",
]

_EMAIL_ADJECTIVES = [
    "bright", "swift", "cool", "dark", "fast", "keen", "bold", "calm",
    "warm", "wise", "fair", "pure", "free", "wild", "soft",
]

_EMAIL_NOUNS = [
    "fox", "star", "wave", "rock", "leaf", "bird", "wolf", "hawk",
    "bear", "tiger", "lion", "eagle", "river", "cloud", "storm",
]


# ── Seed helpers ──────────────────────────────────────────────────────────────

def _seed(key: bytes, value: str) -> bytes:
    return hmac.new(key, value.encode(), hashlib.blake2b).digest()


def _pick(lst: list, seed: bytes, offset: int = 0) -> str:
    idx = struct.unpack_from(">I", seed, offset % (len(seed) - 4))[0]
    return lst[idx % len(lst)]


def _digits(seed: bytes, n: int, offset: int = 0) -> str:
    out = []
    for i in range(n):
        b = seed[(offset + i) % len(seed)]
        out.append(str(b % 10))
    return "".join(out)


# ── FPE generators ────────────────────────────────────────────────────────────

def fpe_name(original: str, seed: bytes) -> str:
    first = _pick(_FIRST_NAMES, seed, 0)
    last  = _pick(_LAST_NAMES,  seed, 4)
    # Try to match original case pattern
    if original.isupper():
        return f"{first.upper()} {last.upper()}"
    if original.islower():
        return f"{first.lower()} {last.lower()}"
    return f"{first} {last}"


def fpe_email(original: str, seed: bytes) -> str:
    adj    = _pick(_EMAIL_ADJECTIVES, seed, 0)
    noun   = _pick(_EMAIL_NOUNS,      seed, 4)
    digits = _digits(seed, 3, 8)
    domain = _pick(_EMAIL_DOMAINS,    seed, 12)
    # Preserve subdomain if present (e.g. user@corp.example.com)
    at = original.find("@")
    if at > 0 and original.count(".") >= 2:
        parts = original[at + 1:].split(".")
        if len(parts) >= 3:
            domain = ".".join([_pick(_EMAIL_DOMAINS, seed, 16).split(".")[0]] + parts[-2:])
    return f"{adj}{noun}{digits}@{domain}"


def fpe_phone(original: str, seed: bytes) -> str:
    digits = _digits(seed, 10, 0)
    # Detect and preserve format
    if original.startswith("+"):
        # International format — keep country code length, replace rest
        cc_end = 2 if original[1].isdigit() else 3
        cc = original[:cc_end]
        rest = digits[:7]
        return f"{cc}-{rest[:3]}-{rest[3:]}"
    if "(" in original:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:10]}"
    sep = "-" if "-" in original else ("." if "." in original else " ")
    return f"{digits[:3]}{sep}{digits[3:6]}{sep}{digits[6:10]}"


def fpe_ssn(original: str, seed: bytes) -> str:
    d = _digits(seed, 9, 0)
    # Avoid real-looking reserved ranges (000, 666, 900-999 for area)
    area = str((int(d[:3]) % 899) + 1).zfill(3)
    if area in ("000", "666"):
        area = "123"
    grp  = str((int(d[3:5]) % 99) + 1).zfill(2)
    seq  = str((int(d[5:9]) % 9999) + 1).zfill(4)
    return f"{area}-{grp}-{seq}"


def _luhn_digit(digits: str) -> int:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 0:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return (10 - total % 10) % 10


def fpe_credit_card(original: str, seed: bytes) -> str:
    clean = re.sub(r"\D", "", original)
    d = _digits(seed, 16, 0)
    # Detect card network by original prefix
    if clean.startswith("4"):
        prefix = "4"
    elif clean[:2] in [str(x) for x in range(51, 56)]:
        prefix = clean[:2]
    elif clean.startswith("34") or clean.startswith("37"):
        prefix = clean[:2]
    else:
        prefix = "4"
    body = prefix + d[:len(clean) - len(prefix) - 1]
    check = str(_luhn_digit(body))
    raw = body + check
    # Reformat to match original spacing
    fmt_match = re.match(r"(\d{4})[\s\-](\d{4})[\s\-](\d{4})[\s\-](\d+)", original)
    if fmt_match:
        sep = "-" if "-" in original else " "
        return f"{raw[:4]}{sep}{raw[4:8]}{sep}{raw[8:12]}{sep}{raw[12:]}"
    return raw


def fpe_ip(original: str, seed: bytes) -> str:
    d = _digits(seed, 12, 0)
    octets = [
        str(int(d[0:3]) % 223 + 1),
        str(int(d[3:6]) % 254 + 1),
        str(int(d[6:9]) % 254 + 1),
        str(int(d[9:12]) % 254 + 1),
    ]
    return ".".join(octets)


# ── Dispatch ──────────────────────────────────────────────────────────────────

_GENERATORS = {
    "NAME":        fpe_name,
    "PERSON":      fpe_name,
    "EMAIL":       fpe_email,
    "EMAIL_ADDRESS": fpe_email,
    "PHONE":       fpe_phone,
    "PHONE_NUMBER": fpe_phone,
    "SSN":         fpe_ssn,
    "US_SSN":      fpe_ssn,
    "CREDIT_CARD": fpe_credit_card,
    "IP_ADDRESS":  fpe_ip,
}


def generate_fpe(entity_type: str, original: str, vault_key: bytes) -> str:
    """Return a deterministic format-preserving replacement for *original*."""
    s = _seed(vault_key, original)
    gen = _GENERATORS.get(entity_type.upper())
    if gen:
        return gen(original, s)
    # Fallback: alphanumeric-preserving shuffle
    result = list(original)
    letters = [c for c in original if c.isalpha()]
    digits  = [c for c in original if c.isdigit()]
    li = di = 0
    fake_letters = list(_pick(_FIRST_NAMES, s, 0) + _pick(_LAST_NAMES, s, 4))
    fake_digits  = list(_digits(s, 20))
    for i, c in enumerate(original):
        if c.isalpha():
            result[i] = fake_letters[li % len(fake_letters)].upper() if c.isupper() else fake_letters[li % len(fake_letters)].lower()
            li += 1
        elif c.isdigit():
            result[i] = fake_digits[di % len(fake_digits)]
            di += 1
    return "".join(result)
