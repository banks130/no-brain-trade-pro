# FORCE ADD YOURSELF TO GET ALERTS
YOUR_TELEGRAM_ID = 123456789  # CHANGE THIS TO YOUR ACTUAL ID

async with SessionLocal() as db:
    user = await db.get(User, YOUR_TELEGRAM_ID)
    if not user:
        db.add(User(
            telegram_id=YOUR_TELEGRAM_ID,
            username="admin",
            tier="pro",
            alerts_enabled=True,
            is_active=True
        ))
        await db.commit()
        print(f"✅ Added user {YOUR_TELEGRAM_ID} - you will get alerts")
    else:
        user.alerts_enabled = True
        user.tier = "pro"
        await db.commit()
        print(f"✅ Updated user {YOUR_TELEGRAM_ID} - alerts ON")
