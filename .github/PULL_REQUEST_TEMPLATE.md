# Pull Request

Thanks for contributing! Please fill in the sections below — the more
context you give, the faster the review.

## Summary

One-paragraph description of the change. What does it do, and why?

## Related issue

- Fixes #
- Refs #

(Use `Closes #123` if this PR resolves an open issue. The GitHub
issue will auto-close on merge.)

## Type of change

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds capability)
- [ ] Breaking change (existing users would need to do something)
- [ ] Documentation only
- [ ] Refactor / cleanup (no behavior change)
- [ ] CI / tooling / infrastructure

## Area(s) affected

- [ ] `web/` (React UI + Pages Functions)
- [ ] `data/` (Python pipeline)
- [ ] `shared/schema/` (cross-runtime contract)
- [ ] `docs/` (project documentation)
- [ ] `.github/` (workflows + community files)

## Test plan

How did you verify the change works? What tests did you run?

- [ ] `cd web && npm test` → all assertions pass
- [ ] `cd web && npm run build` → clean
- [ ] `cd data && pytest` → all tests pass
- [ ] Live verified at https://start.magi.website/
- [ ] Other (describe below)

## Screenshots / output

For UI changes, paste a before/after screenshot or curl transcript.
For new generators, paste a representative output sample.

## Checklist

- [ ] I have read [CONTRIBUTING.md](../blob/main/CONTRIBUTING.md)
- [ ] My commits follow Conventional Commits (`feat:`, `fix:`, etc.)
- [ ] I have added tests covering the change
- [ ] New strings go through the en + zh locale files
- [ ] No new secrets, raw keys, or env-var literals in code
- [ ] If I added a new Token Factory or model provider, I added:
  - [ ] generator in `web/functions/lib/generators/<id>.ts`
  - [ ] registration in `web/functions/lib/generators/index.ts`
  - [ ] agent-prompt variant in `web/functions/lib/generators/agentPrompt.ts`
  - [ ] unit tests in `web/src/__tests__/`
  - [ ] a row in `tools/one-shot/factories/<id>.txt` (if generating)
- [ ] I have updated the relevant docs in `docs/`
- [ ] My branch is rebased on `main` (no merge commits in the PR)

## Notes for reviewers

Anything reviewers should know — known caveats, follow-up work,
dependencies, perf / cost impact, security considerations.