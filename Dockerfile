FROM python:2.7-onbuild
ADD . /usr/src/app/
EXPOSE 8080
RUN python setup.py install