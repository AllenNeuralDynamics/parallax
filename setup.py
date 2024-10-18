from setuptools import setup

if __name__ == "__main__":
    setup(
        name='parallax',
        entry_points={
            'console_scripts': [
                'parallax = parallax.__main__:main'
            ],
        },
    )