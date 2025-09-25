from datetime import datetime, timezone, timedelta

# ✅ 1. UTC 현재 시간 (Python 3.12 기준)
utc_now = datetime.now(timezone.utc)
print("✅ Python 현재 시간 (UTC):", utc_now)

# ✅ 2. KST 변환 (UTC+9)
KST = timezone(timedelta(hours=9))
kst_now = utc_now.astimezone(KST)
print("✅ Python 한국 시간 (KST):", kst_now)
