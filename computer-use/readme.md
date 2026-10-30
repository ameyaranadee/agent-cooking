# Computer Use Agents in Daytona Sandboxes

Computer Use tool primitives to drive a desktop: screenshot, click, type, scroll, press keys

How does the Daytona sandbox work?

- wraps a Linux desktop (browser included) in a Python SDK that exposes these primitives
- thin adapter implementing Agent SDK's `AsyncComputer` interface plugs the sandbox into the tool

How does the agent work?

- agent loop runs in the notebook; sandbox does actual clicking and typing

# Usecase

- form filling; served inside sandbox on `localhost:8080`
- same pattern works for any task you’d describe as “open an app, navigate somewhere, interact with the screen”: testing UI flows end-to-end, driving legacy desktop software, or any workflow that only exists as a human-facing interface.

# Agent automation

In this usecase, we have:

- HTML registration form with fields covering text inputs, emails, phone, dates, dropdowns, radio groups, checkbox group and text area
- includes client-side validation and confirmation to know if run succeeded

## Approach

- `APPLICANT_DATA`: Facts agent will enter; loaded from .txt file
- `INSTRUCTIONS`: System prompt for form filling guidance
- `TASK`: User turn to start run
