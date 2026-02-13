# ui/choose_experience.py
"""
Choose UI mode for this device (mobile vs desktop). Stored in browser storage
so the same user can have desktop on PC and mobile on phone.
"""
from nicegui import ui

from backend.auth import get_current_user


@ui.page('/choose-experience')
def choose_experience_page():
    """Let user choose mobile or desktop layout for this device only."""
    user_id = get_current_user()
    if user_id is None:
        ui.navigate.to('/login')
        return

    def set_mode(ui_mode: str, mobile_version: str = ''):
        # Pass in URL so index can set storage before rendering (avoids race with storage sync)
        if ui_mode == 'mobile' and mobile_version in ('a', 'b'):
            ui.navigate.to(f'/?ui_mode=mobile&mobile_version={mobile_version}')
        else:
            ui.navigate.to(f'/?ui_mode={ui_mode}')

    with ui.column().classes('w-full max-w-md mx-auto mt-16 gap-6'):
        ui.label('How will you use the app on this device?').classes(
            'text-2xl font-bold text-center'
        )
        ui.label(
            'This choice is saved for this device only. Your phone and computer can use different layouts.'
        ).classes('text-gray-600 text-center')

        with ui.card().classes('w-full p-6 gap-4'):
            ui.button(
                'Use on this device: Desktop',
                on_click=lambda: set_mode('desktop'),
                icon='computer',
            ).classes('w-full text-lg py-3')
            ui.button(
                'Use on this device: Mobile (Version A)',
                on_click=lambda: set_mode('mobile', 'a'),
                icon='phone_android',
            ).classes('w-full text-lg py-3')
            ui.button(
                'Use on this device: Mobile (Version B)',
                on_click=lambda: set_mode('mobile', 'b'),
                icon='apps',
            ).classes('w-full text-lg py-3')

        ui.label('You can change this later in Settings.').classes(
            'text-sm text-gray-500 text-center'
        )
