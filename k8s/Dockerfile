FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim AS builder

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        git gettext \
        libmariadb-dev libpq-dev libmemcached-dev build-essential \
        nodejs npm && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /pretalx/
COPY _build /pretalx/_build
COPY src /pretalx/src

RUN uv pip install --system --no-cache-dir -U pip setuptools wheel  && \
    uv pip install --system --no-cache-dir -e /pretalx/[mysql,postgres,redis] && \
    uv pip install --system --no-cache-dir pylibmc gunicorn && \
    # Forked from adamskrz/pretalx-social-auth with a fix for Django form renderer compat (pretalx 2026.1+)
    # Revert when upstream has the fix in place
    uv pip install --system --no-cache-dir git+https://github.com/dennorske/pretalx-social-auth.git@e8715d83c7c2d72f5f6c61cd42211b5b68ac11fe

RUN python3 -m pretalx rebuild && \
    rm -f /pretalx/src/pretalx.cfg /pretalx/src/data/.secret


FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gettext locales \
        libmariadb3 libpq5 libmemcached11t64 \
        supervisor && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    dpkg-reconfigure locales && \
    locale-gen C.UTF-8 && \
    /usr/sbin/update-locale LANG=C.UTF-8 && \
    mkdir /etc/pretalx /data /public && \
    groupadd -g 999 pretalxuser && \
    useradd -r -u 999 -g pretalxuser -d /pretalx -ms /bin/bash pretalxuser

ENV LC_ALL=C.UTF-8

COPY --from=builder /usr/local/lib/python3.14/site-packages /usr/local/lib/python3.14/site-packages
COPY --from=builder /usr/local/bin/gunicorn /usr/local/bin/celery /usr/local/bin/
COPY --from=builder /pretalx /pretalx

COPY k8s/deployment/docker/supervisord.conf /etc/supervisord.conf
COPY k8s/deployment/docker/pretalx.bash /usr/local/bin/pretalx
RUN chmod 755 /usr/local/bin/pretalx

RUN chown -R pretalxuser:pretalxuser /pretalx /data /public /etc/pretalx

USER pretalxuser

VOLUME ["/etc/pretalx", "/data", "/public"]
EXPOSE 80
ENTRYPOINT ["pretalx"]
CMD ["all"]