.PHONY: verify-publish verify-publish-full

verify-publish:
	./scripts/verify_publish.sh fast

verify-publish-full:
	./scripts/verify_publish.sh full
