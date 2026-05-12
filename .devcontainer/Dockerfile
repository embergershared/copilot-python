FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

USER root

RUN set -eux; \
    install -d -m 0755 /usr/share/keyrings; \
    curl -fsSL https://dl.yarnpkg.com/debian/pubkey.gpg | gpg --dearmor --yes -o /usr/share/keyrings/yarn-archive-keyring.gpg; \
    chmod 0644 /usr/share/keyrings/yarn-archive-keyring.gpg
