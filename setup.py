from setuptools import find_packages, setup


if __name__ == "__main__":
    setup(
        version="0.1",
        name="pyinfra-okd4",
        packages=find_packages(),
        install_requires=("pyinfra",),
        package_data={"pyinfra_okd4": ["files/*", "templates/*"]},
        include_package_date=True,
    )
