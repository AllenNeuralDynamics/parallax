from setuptools import setup, find_packages

if __name__ == "__main__":
    setup(
        name='parallax',
        packages=find_packages(exclude=["tests", "tests.*"]),
        entry_points={
            'console_scripts': [
                'parallax = parallax.__main__:main'
            ],
        },
    )