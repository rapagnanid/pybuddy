"""Desktop notifications for PyBuddy."""


def notify(title: str, message: str):
    """Send a desktop notification. Fails silently if not supported."""
    try:
        from plyer import notification

        notification.notify(
            title=title,
            message=message,
            app_name="PyBuddy",
            timeout=5,
        )
    except Exception:
        # Desktop notifications are best-effort
        pass
