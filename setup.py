import os
from setuptools import find_packages, setup

with open(os.path.join(os.path.dirname(__file__), 'README.md')) as readme:
    README = readme.read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(
    name='msgflo',
    version='0.0.13',
    packages=find_packages(),
    include_package_data=True,
    license='MIT License',  # example license
    description='Simple message queueing for AMQP and MQTT',
    long_description=README,
    url='https://msgflo.org',
    author='Jon Nordby',
    author_email='jononor@gmail.com',
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        # Replace these appropriately if you are stuck on Python 2.
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 2.6',
        'Topic :: Internet :: WWW/HTTP',
    ],
    install_requires=[
        "gevent >= 1.0.2",
        "haigha >= 0.8.0",
        "paho-mqtt >= 1.1",
    ],
    scripts=[
        'bin/msgflo-python'
    ],
)
