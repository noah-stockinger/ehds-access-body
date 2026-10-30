# RStudio Server (AGPL-3) for the secure processing environment, with the DuckDB driver (MIT). See src/hdab/rstudio.py.
FROM rocker/rstudio:4.5.1
RUN install2.r --error --skipinstalled DBI duckdb
# The session runs with --network none: the browser reaches it over this socket through docker/rstudio-proxy.
# DISABLE_AUTH=true replaces rserver.conf with disable_auth_rserver.conf, so the socket must be in both.
RUN printf '\nwww-socket=/run/rstudio-socket/rstudio.sock\n' | tee -a /etc/rstudio/rserver.conf /etc/rstudio/disable_auth_rserver.conf
# Convenience only, these do not close RStudio's download routes: the barriers are the missing network and the proxy.
RUN printf '%s\n' allow-file-downloads=0 allow-file-uploads=0 allow-publish=0 allow-external-publish=0 allow-package-installation=0 allow-vcs=0 >> /etc/rstudio/rsession.conf
COPY Rprofile /home/rstudio/.Rprofile
RUN chown rstudio:rstudio /home/rstudio/.Rprofile
