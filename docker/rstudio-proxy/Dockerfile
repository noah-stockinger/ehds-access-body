# The only way into an RStudio session (src/hdab/rstudio.py): refuses RStudio's file download routes (S-020, S-081).
FROM nginx:1.29-alpine
COPY default.conf /etc/nginx/conf.d/default.conf
# The session's socket belongs to root.
RUN sed -i 's/^user .*/user root;/' /etc/nginx/nginx.conf
