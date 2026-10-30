"""python-for-android recipe for pygame-ce (the APK's pygame).

python-for-android only ships a recipe for the old upstream pygame
2.1.0, and the game is written against pygame-ce.  This is that recipe
moved to pygame-ce's setup.py build (still in its sdist next to the
meson one); buildozer.spec points ``p4a.local_recipes`` here.

Fixes for cross-compiling on a CI runner:

* setup.py adds ``-mavx2`` when the *build* machine is x86; setting
  ``MAC_ARCH=arm64`` is its own switch to turn that off.
* setup.py adds ``-Werror`` when ``CI`` is set (as on GitHub Actions),
  which an NDK build's harmless warnings would break; ``CI`` is dropped.
* pip installs the built package with the build backend named in
  pyproject.toml (meson-python), so that file is swapped for one naming
  setuptools, which runs the same setup.py.
"""

from os.path import join

from pythonforandroid.recipe import CompiledComponentsPythonRecipe
from pythonforandroid.toolchain import current_directory

PYPROJECT = """\
[build-system]
requires = ["setuptools", "wheel", "cython<=3.1.4"]
build-backend = "setuptools.build_meta:__legacy__"
"""


class PygameCeRecipe(CompiledComponentsPythonRecipe):
    version = "2.5.6"
    url = ("https://files.pythonhosted.org/packages/source/p/pygame-ce/"
           "pygame_ce-{version}.tar.gz")

    site_packages_name = "pygame"
    name = "pygame-ce"
    conflicts = ["pygame"]

    depends = ["sdl2", "sdl2_image", "sdl2_mixer", "sdl2_ttf", "setuptools",
               "jpeg", "png"]
    hostpython_prerequisites = ["setuptools", "cython<=3.1.4"]
    call_hostpython_via_targetpython = False  # Due to setuptools
    install_in_hostpython = False

    def prebuild_arch(self, arch):
        super().prebuild_arch(arch)
        with current_directory(self.get_build_dir(arch.arch)):
            with open("pyproject.toml", "w") as f:
                f.write(PYPROJECT)
            with open(join("buildconfig", "Setup.Android.SDL2.in")) as f:
                setup_template = f.read()
            env = self.get_recipe_env(arch)
            env["ANDROID_ROOT"] = join(self.ctx.ndk.sysroot, "usr")

            png = self.get_recipe("png", self.ctx)
            png_lib_dir = join(png.get_build_dir(arch.arch), ".libs")
            png_inc_dir = png.get_build_dir(arch)

            jpeg = self.get_recipe("jpeg", self.ctx)
            jpeg_inc_dir = jpeg_lib_dir = jpeg.get_build_dir(arch.arch)

            sdl_mixer_includes = ""
            sdl2_mixer_recipe = self.get_recipe("sdl2_mixer", self.ctx)
            for include_dir in sdl2_mixer_recipe.get_include_dirs(arch):
                sdl_mixer_includes += f"-I{include_dir} "

            sdl2_image_includes = ""
            sdl2_image_recipe = self.get_recipe("sdl2_image", self.ctx)
            for include_dir in sdl2_image_recipe.get_include_dirs(arch):
                sdl2_image_includes += f"-I{include_dir} "

            setup_file = setup_template.format(
                sdl_includes=(
                    " -I" + join(self.ctx.bootstrap.build_dir, "jni", "SDL", "include")
                    + " -L" + join(self.ctx.bootstrap.build_dir, "libs", str(arch))
                    + " -L" + png_lib_dir + " -L" + jpeg_lib_dir
                    + " -L" + arch.ndk_lib_dir_versioned),
                sdl_ttf_includes="-I" + join(self.ctx.bootstrap.build_dir, "jni", "SDL2_ttf"),
                sdl_image_includes=sdl2_image_includes,
                sdl_mixer_includes=sdl_mixer_includes,
                jpeg_includes="-I" + jpeg_inc_dir,
                png_includes="-I" + png_inc_dir,
                freetype_includes="",
            )
            with open("Setup", "w") as f:
                f.write(setup_file)

    def get_recipe_env(self, arch, **kwargs):
        env = super().get_recipe_env(arch, **kwargs)
        env["USE_SDL2"] = "1"
        env["PYGAME_CROSS_COMPILE"] = "TRUE"
        env["PYGAME_ANDROID"] = "TRUE"
        env["MAC_ARCH"] = "arm64"     # no -mavx2 (see the module docstring)
        env.pop("CI", None)           # no -Werror
        return env


recipe = PygameCeRecipe()
