FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

USER root

RUN set -eux; \
    install -d -m 0755 /usr/share/keyrings; \
    curl -fsSL https://dl.yarnpkg.com/debian/pubkey.gpg | gpg --dearmor --yes -o /usr/share/keyrings/yarn-archive-keyring.gpg; \
    chmod 0644 /usr/share/keyrings/yarn-archive-keyring.gpg; \
    curl -fsSL https://apt.releases.hashicorp.com/gpg | gpg --dearmor --yes -o /usr/share/keyrings/hashicorp-archive-keyring.gpg; \
    chmod 0644 /usr/share/keyrings/hashicorp-archive-keyring.gpg; \
    . /etc/os-release; \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com ${VERSION_CODENAME} main" > /etc/apt/sources.list.d/hashicorp.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends terraform; \
    rm -rf /var/lib/apt/lists/*
