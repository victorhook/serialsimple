from setuptools import setup, find_packages
import app


setup(
    name=app.APP_NAME,
    version=app.APP_VERSION,
    author=app.APP_AUTHOR,
    license='MIT',
    packages=find_packages('.'),
    url='https://github.com/victorhook/serialsimple',
    keywords='serial gui simple',
)
