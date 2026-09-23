# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **UI/UX Testing:** Playwright end-to-end tests for both admin and buyer portals.
- **Performance:** `locustfile.py` included in backend for load testing.
- **Data Protection:** Fernet symmetric at-rest encryption added to secure document blobs in the database.
- **Data Retention:** Automated daily purge implemented for cancelled orders (>90 days) and expired documents (>30 days).
- **Enterprise SSO:** Added "Enterprise Sign-In (SSO)" button in the buyer portal.
- **Accessibility:** Ensure ARIA and `htmlFor` configurations are complete in form components.
- **Release Management:** `.github/workflows/ci.yml` added for linting and testing in CI/CD pipelines.

## [1.0.0] - Initial Release
### Added
- Core order management workflow
- Supabase Auth integration
- React Next.js frontends and Python HTTP API
