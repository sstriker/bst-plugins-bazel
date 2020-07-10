# Copyright 2020 Sander Striker
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

# XXX Redone from scratch for educational and exploration purposes:
# XXX https://gitlab.com/BuildStream/buildstream/-/issues/529

"""
bazel - TODO
====================================
``bazel`` element

TODO...

This plugin provides the following ``config`` options to modify
behavior.

The default configuration is as such:
  .. literalinclude:: ../../../src/bst_plugins_bazel/elements/bazel.yaml
     :language: yaml
"""

import collections
from enum import Enum
import os
import re

from buildstream import BuildElement, Scope, ElementError
from buildstream import SandboxFlags


def _exts2re(**extmap):
    return re.compile(
        r".*\.({})$".format(
            "|".join(
                [
                    "(?P<{}>{})".format(
                        name, "|".join(["({})".format(ext) for ext in exts])
                    )
                    for name, exts in extmap.items()
                ]
            )
        )
    )


class BazelElement(BuildElement):
    # pylint: disable=too-many-instance-attributes

    BST_MIN_VERSION = "2.0"

    # BuildTrees do not make particular sense in the context of Bazel.
    BST_NEVER_CACHE_BUILDTREES = True

    # XXX TODO CORE ENHANCEMENT
    # XXX Indicate that bazel would like to use an element cache directory
    BST_ELEMENT_CACHE = True

    # XXX Efficiency.
    BST_ELEMENT_STAGE_READ = False
    # XXX Trust, reproducibility
    BST_ELEMENT_STAGE_WRITE = True

    # XXX Efficiency.
    BST_ELEMENT_ASSEMBLE_READ = False
    # XXX Trust, reproducibility
    BST_ELEMENT_ASSEMBLE_WRITE = False

    def configure(self, node):
        super().configure(node)

        # XXX: This would be better as actual configuration(?)
        workspace_mode = self.get_variable("bazel-workspace-mode")
        try:
            self.workspace_mode = _WorkspaceMode(workspace_mode)
        except ValueError:
            raise ElementError(
                "Invalid bazel-workspace-mode: {} [all,external,single]".format(
                    workspace_mode
                )
            )

        dependency_mode = self.get_variable("bazel-dependency-mode")
        try:
            self.dependency_mode = _DependencyMode(dependency_mode)
        except ValueError:
            raise ElementError(
                "Invalid bazel-dependency-mode: {} [artifact,source]".format(
                    dependency_mode
                )
            )

        self.bazel_build_root = self.get_variable("bazel-build-root")

        self.bazel_cache_directory = self.get_variable("bazel-cache-directory")

        # TODO configure bazel for remote asset caching, pointing to the
        # TODO locally exposed buildbox-casd actioncache
        # TODO Tell the sandbox to expose the actioncache inside the sandbox
        # TODO
        # TODO
        # TODO configure bazel to use the xattr attribute that buildbox-fuse
        # TODO exposes (user.checksum.sha256)
        # TODO see: https://github.com/bazelbuild/bazel/pull/11662
        #
        # bazel
        # --bazelrc=/dev/null
        # --output_user_root={} self.bazel_cache_directory

    def get_unique_key(self):
        dictionary = super().get_unique_key()
        dictionary.update(
            {
                "workspace-mode": self.workspace_mode.value,
                "dependency-mode": self.dependency_mode.value,
            }
        )
        return dictionary

    def configure_sandbox(self, sandbox):
        super().configure_sandbox(sandbox)

        # Make sure the bazel cache directory exists
        sandbox.mark_directory(self.bazel_cache_directory)

        # XXX This is heavily relying on private APIs, this needs to be
        # XXX done in buildelement.py:BuildElement rather than here.
        # Expose a cache directory to the sandbox that persists between
        # runs.  This should obviously only be done by plugins that indicate
        # that they want this.  See BST_ELEMENT_CACHE.
        # TODO have project configuration to disable/enable
        # See: https://gitlab.com/BuildStream/buildstream/-/issues/529#note_91889061
        if self.BST_ELEMENT_CACHE:  # and not configured to be disabled
            context = self._get_context()
            bazel_element_cachedir = os.path.join(
                context.cachedir, "elements", self.get_kind()
            )
            os.makedirs(bazel_element_cachedir, exist_ok=True)

            # Expose the bazel cache directory
            # XXX add method Sandbox.mount_cache(source, destination), where implementations _can_
            # XXX be a no-op
            sandbox._set_mount_source(  # pylint: disable=protected-access
                self.bazel_cache_directory, bazel_element_cachedir
            )

    # TODO refactor
    def stage(self, sandbox):  # pylint: disable=too-many-branches
        """The workhorse of the bazel element plugin"""

        basedir = sandbox.get_virtual_directory()
        workspace_file_content = ""

        source_elements = []

        # Stage deps in the sandbox root, in the order buildsteam
        # gives us.  Keep track of what we did so we can run integration
        # commands after in the same order.
        staged_artifacts = []
        with self.timed_activity("Staging dependencies", silent_nested=True):
            for dep in self.dependencies(Scope.BUILD):

                # Stage tools regularly
                if self._is_tool(dep):
                    staged_artifacts.append(dep)
                    dep.stage_artifact(sandbox)

                # Staging bazel dependencies
                elif self._is_bazel_kind(dep):
                    if self.dependency_mode == _DependencyMode.SOURCE:
                        source_elements.append(dep)
                        # Defer staging sources
                    elif self.dependency_mode == _DependencyMode.ARTIFACT:
                        element_dir = dep.get_variable("build-root")
                        dep.stage_artifact(sandbox, path=element_dir)
                        if self.workspace_mode == _WorkspaceMode.ALL:
                            workspace_file_content += self._generate_local_repository(
                                dep, element_dir
                            )

                # Stage input dependencies
                else:
                    if self.workspace_mode == _WorkspaceMode.SINGLE:
                        element_dir = dep.get_variable("build-root")
                        # TODO make include, exclude domains configurable
                        result = dep.stage_artifact(sandbox, path=element_dir)
                        manifest = result.files_written
                        # TODO if 'BUILD' or 'BUILD.bazel' already in manifest, we're done

                        build_file_content = self._generate_build_content(
                            dep, manifest
                        )
                        if build_file_content:
                            vdir = basedir.descend(
                                *element_dir.lstrip("/").split("/"),
                                create=True
                            )
                            with vdir.open_file("BUILD.bazel", mode="w") as f:
                                f.write(build_file_content)

                    if self.workspace_mode in (
                        _WorkspaceMode.EXTERNAL,
                        _WorkspaceMode.ALL,
                    ):
                        staged_artifacts.append(dep)
                        # TODO make include, exclude domains configurable
                        result = dep.stage_artifact(sandbox)
                        manifest = result.files_written

                        build_file_content = self._generate_build_content(
                            dep, manifest
                        )
                        if build_file_content:
                            workspace_file_content += self._generate_new_local_repository(
                                dep,
                                dep.get_variable("prefix"),
                                build_file_content,
                            )

        # Run any integration commands provided by the dependencies
        # once they are all staged and ready
        with sandbox.batch(SandboxFlags.NONE, label="Integrating sandbox"):
            for dep in staged_artifacts:
                dep.integrate(sandbox)

        # Stage bazel elements as source
        #
        source_elements.append(self)
        with self.timed_activity("Staging sources", silent_nested=True):
            for element in source_elements:
                # NOTE: we assume that %build-root is different for each element
                element_dir = element.get_variable("build-root")
                element.stage_sources(sandbox, element_dir)

                if self.workspace_mode == _WorkspaceMode.ALL:
                    workspace_file_content += self._generate_local_repository(
                        dep, element_dir
                    )

        # Generate the WORKSPACE file
        if self.workspace_mode == _WorkspaceMode.ALL:
            workspace_dir = self.bazel_build_root
        elif self.workspace_mode in (
            _WorkspaceMode.SINGLE,
            _WorkspaceMode.EXTERNAL,
        ):
            # NOTE: we assume build-root has a common parent directory between elements
            workspace_dir = self.get_variable("build-root")
            workspace_dir = workspace_dir.rsplit("/", maxsplit=1)[0]

        vdir = basedir.descend(
            *workspace_dir.lstrip("/").split("/"), create=True
        )
        with vdir.open_file("WORKSPACE.bazel", mode="w") as f:
            f.write(workspace_file_content)

    def _is_bazel_kind(self, element: "Element"):
        # This element (self) is of the bazel kind, use that to test
        return self.get_kind() == element.get_kind()

    def _is_tool(self, element):  # pylint: disable=no-self-use,unused-argument
        # XXX TODO CORE ENHANCEMENT
        # XXX Be able to distinguish tool dependencies from build inputs
        return False

    @staticmethod
    def _generate_local_repository(element, path):
        return """local_repository(
    name = "{name}",
    path = "{path}"
)

""".format(
            name=element.normal_name, path=path
        )

    @staticmethod
    def _generate_new_local_repository(element, path, build_file_content):
        return """new_local_repository(
    name = "{name}",
    path = "{path}",
    build_file_content = \"""{content}\"""
)

""".format(
            name=element.normal_name, path=path, content=build_file_content
        )

    def _generate_build_content(self, element, manifest):
        # Based on the files, generate some BUILD.bazel content
        # Return None if we don't want to generate a BUILD file for this element

        # TODO potentially use pkgconfig instead if there is a .pc file available?
        # TODO There appears to be a bazel rule available to do just that.

        # NOTE: Assume manifest is actually in sorted order
        # TODO: if there is already a BUILD or BUILD.bazel, return None
        categories = collections.defaultdict(list)
        for path in manifest:
            match = self._RE_EXTS.match(path)
            if match is None:
                continue
            for group in ("srcs", "hdrs"):
                if match[group]:
                    categories[group].append(path)

        hdrs = categories["hdrs"]
        srcs = categories["srcs"]
        if not hdrs and not srcs:
            # Nothing to define
            return None

        # TODO rewrite this to make it more legible
        build_file_content = """load("@rules_cc//cc:defs.bzl")

cc_library(
    name = "{name}",
""".format(
            name=element.normal_name
        )

        if hdrs:
            build_file_content += """    hdrs = [
        {hdrs},
    ],
""".format(
                hdrs=",\n        ".join(['"{}"'.format(hdr) for hdr in hdrs])
            )

        if srcs:
            build_file_content += """    srcs = [
        {srcs},
    ],
""".format(
                srcs=",\n        ".join(['"{}"'.format(src) for src in srcs])
            )

        build_file_content += """    include_prefix = "{include_dir}",
    strip_include_prefix = "{include_dir}",
    copts = [
        "-I{include_dir}"
    ],
""".format(
            include_dir=element.get_variable("includedir")
        )

        build_file_content += """    deps = [
"""

        for dep in element.dependencies(Scope.RUN):
            # Skip the element itself
            if dep == element:
                continue

            build_file_content += """        "{}",
""".format(
                self._generate_dependency_label(dep)
            )

        build_file_content += """    ],
)
"""
        return build_file_content

    def _generate_dependency_label(self, element):
        if self.workspace_mode == _WorkspaceMode.ALL:
            repository = element.normal_name
        elif (
            self.workspace_mode == _WorkspaceMode.EXTERNAL
            and not self._is_bazel_kind(element)
        ):
            repository = element.normal_name
        else:
            # In SINGLE mode or EXTERNAL where the dependency is of bazel kind,
            # use the main repository
            repository = ""
        return "@{repository}//{package}".format(
            repository=repository, package=element.normal_name
        )

    def _workspace_name(self):
        # Return a normalized workspace name
        # https://docs.bazel.build/versions/master/skylark/lib/globals.html#parameters-35
        name = self.get_variable("project-name")
        return name.replace("-", "_")

    _RE_EXTS = _exts2re(
        hdrs=["h", "hh", "hpp", "hxx", "inc", "inl", "H"],
        srcs=[
            r"c",
            r"cc",
            r"cpp",
            r"cxx",
            r"c\+\+",
            r"C",
            r"S",
            r"a",
            r"pic\.a",
            r"lo",
            r"pic\.lo",
            r"so",
            r"so\..+",
            r"o",
            r"pic\.o",
        ],
    )


# _WorkspaceMode()
#
# How to construct Bazel workspaces
#
class _WorkspaceMode(Enum):

    # Do not create additional workspaces for dependencies
    #
    #   - for each bazel dependency
    #     - stage sources in the dependency buildroot
    #     - generate a local_repository entry in the workspace file
    #   - for each non-bazel dependency
    #     - stage the artifact in the dependency buildroot
    #     - generate a BUILD.bazel file in the dependency buildroot
    #   - for this element stage sources in the buildroot
    #   - generate a WORKSPACE.bazel file in the parent of buildroot
    SINGLE = "single"

    # Create workspaces for non-bazel dependencies
    #
    #   - for each bazel dependency
    #     - stage sources in the dependency buildroot
    #     - generate a local_repository entry in the workspace file
    #   - for each non-bazel dependency
    #     - stage the artifact in its regular location
    #     - generate a new_local_repository entry in the workspace file,
    #       and generate BUILD file content for the entry
    #   - for this element stage sources in the buildroot
    #   - generate a WORKSPACE.bazel file in the parent of buildroot
    EXTERNAL = "external"

    # Every element is seen as its own repository, the workspace
    # will not contain any packages
    #
    #   - for each bazel dependency
    #     - stage sources in the dependency buildroot
    #     - generate a local_repository entry in the workspace file
    #   - for each non-bazel dependency
    #     - stage the artifact in its regular location
    #     - generate a new_local_repository entry in the workspace file,
    #       and generate BUILD file content for the entry
    #   - for this element stage sources in the buildroot
    #     - generate a local_repository entry in the workspace file
    #   - generate a WORKSPACE.bazel file in bazel-buildroot
    #   - use bazel-buildroot as the workdir
    ALL = "all"


# _DependencyMode()
#
# How to stage Bazel dependencies
#
class _DependencyMode(Enum):

    # Stage bazel dependencies as artifacts
    #
    #   - stage each bazel dependency as an artifact
    #     NOTE that we expect a BUILD file at the root of the artifact.
    ARTIFACT = "artifact"

    # Stage bazel dependencies as sources
    #
    #   - stage each bazel dependency as source
    #     The major benefit of this is that it doesn't require any translation
    #     between bazel dependencies.
    #     For efficiency we would want bazel to have access to the actions/
    #     actionresults from the run of the build of the dependency.
    SOURCE = "source"


def setup():
    return BazelElement
