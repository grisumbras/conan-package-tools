import os
import sys
import time
import unittest

from conans import __version__ as client_version
from conans import tools
from conans.model.ref import ConanFileReference
from conans.model.version import Version

from cpt import __version__ as version
from cpt.packager import ConanMultiPackager
from cpt.test.integration.base import BaseTest, PYPI_TESTING_REPO, CONAN_UPLOAD_URL, \
    CONAN_UPLOAD_PASSWORD, CONAN_LOGIN_UPLOAD
from cpt.test.unit.utils import MockCIManager


def is_linux_and_have_docker():
    return tools.os_info.is_linux and tools.which("docker")


class DockerTest(BaseTest):

    @unittest.skipUnless(is_linux_and_have_docker(), "Requires Linux and Docker")
    def test_docker(self):
        if not os.getenv("PYPI_PASSWORD", None):
            return
        self.deploy_pip()
        ci_manager = MockCIManager()
        unique_ref = "zlib/%s" % str(time.time())
        conanfile = """from conans import ConanFile
import os

class Pkg(ConanFile):
    settings = "os", "compiler", "build_type", "arch"

"""
        self.save_conanfile(conanfile)
        the_version = version.replace("-", ".")  # Canonical name for artifactory repo
        pip = "--extra-index-url %s/simple conan-package-tools==%s " % (PYPI_TESTING_REPO, the_version)
        with tools.environment_append({"CONAN_USE_DOCKER": "1",
                                       "CONAN_DOCKER_USE_SUDO": "1",
                                       "CONAN_PIP_PACKAGE": pip,
                                       "CONAN_LOGIN_USERNAME": CONAN_LOGIN_UPLOAD,
                                       "CONAN_USERNAME": "lasote",
                                       "CONAN_UPLOAD": CONAN_UPLOAD_URL,
                                       "CONAN_PASSWORD": CONAN_UPLOAD_PASSWORD,
                                       "CONAN_CONFIG_URL": "https://conan.jfrog.io/conan/"
                                                           "testing_files/empty_zip.zip"}):
            self.packager = ConanMultiPackager(channel="mychannel",
                                               gcc_versions=["6"],
                                               archs=["x86", "x86_64"],
                                               build_types=["Release"],
                                               reference=unique_ref,
                                               ci_manager=ci_manager)
            self.packager.add_common_builds()
            self.packager.run()

        search_pattern = "%s*" % unique_ref
        ref = ConanFileReference.loads("%s@lasote/mychannel" % unique_ref)

        # Remove from remote
        if Version(client_version) < Version("1.7"):
            results = self.api.search_recipes(search_pattern, remote="upload_repo")["results"][0]["items"]
            self.assertEquals(len(results), 1)
            packages = self.api.search_packages(ref, remote="upload_repo")["results"][0]["items"][0]["packages"]
            self.assertEquals(len(packages), 2)
            self.api.authenticate(name=CONAN_LOGIN_UPLOAD, password=CONAN_UPLOAD_PASSWORD,
                                  remote="upload_repo")
            self.api.remove(search_pattern, remote="upload_repo", force=True)
            self.assertEquals(self.api.search_recipes(search_pattern)["results"], [])
        else:
            results = self.api.search_recipes(search_pattern, remote_name="upload_repo")["results"][0]["items"]
            self.assertEquals(len(results), 1)
            if Version(client_version) >= Version("1.12.0"):
                ref = repr(ref)
            packages = self.api.search_packages(ref, remote_name="upload_repo")["results"][0]["items"][0]["packages"]
            self.assertEquals(len(packages), 2)
            self.api.authenticate(name=CONAN_LOGIN_UPLOAD, password=CONAN_UPLOAD_PASSWORD,
                                  remote_name="upload_repo")
            self.api.remove(search_pattern, remote_name="upload_repo", force=True)
            self.assertEquals(self.api.search_recipes(search_pattern)["results"], [])

        # Try upload only when stable, shouldn't upload anything
        with tools.environment_append({"CONAN_USE_DOCKER": "1",
                                       "CONAN_DOCKER_USE_SUDO": "1",
                                       "CONAN_PIP_PACKAGE": pip,
                                       "CONAN_LOGIN_USERNAME": CONAN_LOGIN_UPLOAD,
                                       "CONAN_USERNAME": "lasote",
                                       "CONAN_PASSWORD": CONAN_UPLOAD_PASSWORD,
                                       "CONAN_UPLOAD_ONLY_WHEN_STABLE": "1"}):
            self.packager = ConanMultiPackager(channel="mychannel",
                                               gcc_versions=["6"],
                                               archs=["x86", "x86_64"],
                                               build_types=["Release"],
                                               reference=unique_ref,
                                               upload=CONAN_UPLOAD_URL,
                                               ci_manager=ci_manager)
            self.packager.add_common_builds()
            self.packager.run()

        if Version(client_version) < Version("1.7"):
            results = self.api.search_recipes(search_pattern, remote="upload_repo")["results"]
            self.assertEquals(len(results), 0)
            self.api.remove(search_pattern, remote="upload_repo", force=True)
        else:
            results = self.api.search_recipes(search_pattern, remote_name="upload_repo")["results"]
            self.assertEquals(len(results), 0)
            self.api.remove(search_pattern, remote_name="upload_repo", force=True)


    @unittest.skipUnless(is_linux_and_have_docker(), "Requires Linux and Docker")
    def test_docker_run_options(self):
        conanfile = """from conans import ConanFile
import os

class Pkg(ConanFile):
    settings = "os", "compiler", "build_type", "arch"

    def build(self):
        pass
"""
        self.save_conanfile(conanfile)
        # Validate by Environemnt Variable
        with tools.environment_append({"CONAN_USERNAME": "bar",
                                       "CONAN_DOCKER_IMAGE": "conanio/gcc8",
                                       "CONAN_DOCKER_USE_SUDO": "0",
                                       "CONAN_REFERENCE": "foo/0.0.1@bar/testing",
                                       "CONAN_DOCKER_RUN_OPTIONS": "--network=host, --add-host=google.com:8.8.8.8"
                                       }):
            self.packager = ConanMultiPackager(gcc_versions=["8"],
                                               archs=["x86_64"],
                                               build_types=["Release"],
                                               out=self.output.write)
            self.packager.add({})
            self.packager.run()
            self.assertIn("--network=host --add-host=google.com:8.8.8.8  conanio/gcc8", self.output)

        # Validate by parameter
        with tools.environment_append({"CONAN_USERNAME": "bar",
                                       "CONAN_DOCKER_IMAGE": "conanio/gcc8",
                                       "CONAN_DOCKER_USE_SUDO": "0",
                                       "CONAN_REFERENCE": "foo/0.0.1@bar/testing"
                                       }):

            self.packager = ConanMultiPackager(gcc_versions=["8"],
                                               archs=["x86_64"],
                                               build_types=["Release"],
                                               docker_run_options="--cpus=1",
                                               out=self.output.write)
            self.packager.add({})
            self.packager.run()
            self.assertIn("--cpus=1  conanio/gcc8", self.output)
