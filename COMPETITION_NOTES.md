# GreenShield AI — Competition edition

## Functional modules
- Auth: user registration/login with PBKDF2 password hashes and signed sessions.
- Dashboard: real plant, care and diagnosis counts.
- Plant Doctor: sends uploaded image to NVIDIA via backend; requires valid NVIDIA_API_KEY and model vision support.
- My Plants: CRUD and image upload.
- Health Passport: diagnosis and treatment timeline.
- Recovery Tracker: dated before/after photo pairs.
- Care Calendar: repeating care tasks and completion history.
- AI Recommendations: **schedule-derived suggestions**, not a separate generative AI recommender.
- Language picker: six language choices; **translations are incomplete** for several interface strings.
- Plans: monthly and yearly Free / Pro / Premium demo pricing. All payment buttons are intentionally disabled. No PayPal transactions or recurring billing exist.

## Demo and production caveats
- Start backend and frontend following README. Install dependencies before running.
- Do not claim live NVIDIA diagnosis without testing with a real API key and an image-compatible model.
- This is a competition prototype, not production-hardened: upload privacy, authorization of media files, rate limits, email verification, tests, monitoring, and deployment configuration require work. Uploaded images currently have public URLs.
- Subscription prices are **illustrative**, not actual active offers.
