cmake_minimum_required(VERSION 3.21)
project(decord2 LANGUAGES C CXX)

# ---------------------------------------------------------------------------
# User options & Core Dependencies
# ---------------------------------------------------------------------------
include(cmake/util/Util.cmake)
# Find FFmpeg (required for all builds, regardless of CUDA)
include(cmake/util/FindFFmpeg.cmake)
include(cmake/modules/FFmpeg.cmake)
include(cmake/modules/VideoToolbox.cmake)

decord_option(USE_CUDA "Build with CUDA" OFF)
decord_option(USE_MSVC_MT "Build with MT runtime on MSVC" OFF)
decord_option(USE_VIDEOTOOLBOX "Build with VideoToolbox support (macOS only)" OFF)

# ---------------------------------------------------------------------------
# Source File Discovery
# ---------------------------------------------------------------------------

# Gather all non-CUDA C++ source files first.
file(GLOB_RECURSE DECORD_CORE_SRCS
        "src/runtime/*.cc"
        "src/video/ffmpeg/*.cc"
        "src/video/logging.cc"
        "src/video/storage_pool.cc"
        "src/video/video_interface.cc"
        "src/video/video_loader.cc"
        "src/video/video_reader.cc"
        "src/sampler/*.cc"
        "src/audio/*.cc"
        "src/av_wrapper/*.cc"
        "src/segmenter/*.cc"
)

# Filter out any remaining cuda files just in case (robustness)
if(NOT USE_CUDA)
  list(FILTER DECORD_CORE_SRCS EXCLUDE REGEX "/runtime/cuda/")
endif()


# ---------------------------------------------------------------------------
# Library Target Definition
# ---------------------------------------------------------------------------
add_library(decord SHARED ${DECORD_CORE_SRCS} ${VIDEOTOOLBOX_SRCS})

# --- Modern Target-Based Properties ---

# Set the include directories needed to compile the library
target_include_directories(decord
        PUBLIC
        "${CMAKE_CURRENT_SOURCE_DIR}/include"
        "${CMAKE_CURRENT_SOURCE_DIR}/3rdparty/dlpack/include"
        "${CMAKE_CURRENT_SOURCE_DIR}/3rdparty/dmlc-core/include"
        PRIVATE
        "${CMAKE_CURRENT_SOURCE_DIR}/src"
)

# Link against FFmpeg (always required)
if(FFMPEG_LIBRARIES)
  target_link_libraries(decord
          PRIVATE
          ${FFMPEG_LIBRARIES}
  )
endif()

# Link against macOS frameworks and any extra libs collected by modules
if (DECORD_LINKER_LIBS)
  target_link_libraries(decord PRIVATE ${DECORD_LINKER_LIBS})
endif()

# Set the C++ standard and compiler options
target_compile_features(decord PUBLIC cxx_std_11)

if(MSVC)
  target_compile_definitions(decord PRIVATE -DDECORD_EXPORTS)
  # ... other MSVC options ...
else()
  target_compile_options(decord PRIVATE -fvisibility=hidden -Wall -fPIC)
  target_compile_options(decord PRIVATE $<$<CXX_COMPILER_ID:GNU>:-Wno-unknown-pragmas>)
  target_compile_options(decord PRIVATE $<$<AND:$<CXX_COMPILER_ID:GNU>,$<VERSION_GREATER:$<CXX_COMPILER_VERSION>,7.0>>:-faligned-new>)
  target_link_options(decord PRIVATE -rdynamic)
endif()

# ---------------------------------------------------------------------------
# Optional CUDA Logic (The Modern Way)
# ---------------------------------------------------------------------------
if(USE_CUDA)
  message(STATUS "USE_CUDA is ON. Configuring CUDA support.")

  # Determine CUDA architectures to build for.
  # Priority: CMAKE_CUDA_ARCHITECTURES > CUDA_ARCH > default
  if(NOT DEFINED CMAKE_CUDA_ARCHITECTURES OR CMAKE_CUDA_ARCHITECTURES STREQUAL "")
    if(DEFINED CUDA_ARCH AND NOT CUDA_ARCH STREQUAL "")
      # Parse user-provided CUDA_ARCH (comma or semicolon separated)
      string(REPLACE "," ";" _cuda_arch_list "${CUDA_ARCH}")
      set(CMAKE_CUDA_ARCHITECTURES ${_cuda_arch_list})
      message(STATUS "Using user-specified CUDA architectures: ${CMAKE_CUDA_ARCHITECTURES}")
    else()
      # Use a default list of common architectures.
      # 52 = Maxwell, 60/61 = Pascal, 70 = Volta, 75 = Turing, 80/86 = Ampere, 89 = Ada, 90 = Hopper
      # Note: "native" requires CMake 3.24+ and a GPU present at configure time,
      # so we use explicit architectures for better portability.
      set(CMAKE_CUDA_ARCHITECTURES "52;60;61;70;75;80;86;89;90")
      message(STATUS "Using default CUDA architectures: ${CMAKE_CUDA_ARCHITECTURES}")
    endif()
  else()
    message(STATUS "Using CMAKE_CUDA_ARCHITECTURES: ${CMAKE_CUDA_ARCHITECTURES}")
  endif()

  # 1. Enable the CUDA language. This finds the compiler automatically.
  enable_language(CUDA)
  find_package(CUDAToolkit REQUIRED)

  # 2. Add CUDA-specific source files to our target
  file(GLOB_RECURSE CUDA_RUNTIME_SRCS "src/runtime/cuda/*.cc")
  file(GLOB_RECURSE CUDA_NVDEC_SRCS "src/video/nvcodec/*.cc")
  file(GLOB_RECURSE CUDA_NVDEC_CU_SRCS "src/improc/*.cu")
  target_sources(decord PRIVATE ${CUDA_RUNTIME_SRCS} ${CUDA_NVDEC_SRCS} ${CUDA_NVDEC_CU_SRCS})

  # 3. Add the CUDA compile definition
  target_compile_definitions(decord PRIVATE DECORD_USE_CUDA)

  # 4. Explicitly set CUDA_ARCHITECTURES on the target.
  # This is required because the target was created before enable_language(CUDA),
  # so CMAKE_CUDA_ARCHITECTURES is not automatically applied.
  set_property(TARGET decord PROPERTY CUDA_ARCHITECTURES ${CMAKE_CUDA_ARCHITECTURES})

  # 5. Link against the modern CUDAToolkit imported targets
  # This is much more reliable than using old custom variables.
  target_link_libraries(decord PRIVATE
          CUDAToolkit::cudart
          CUDAToolkit::nvrtc
          CUDAToolkit::cublas
          CUDAToolkit::nvml
  )

  # Find nvcuvid library (required for hardware video decoding)
  find_library(CUDA_NVCUVID_LIBRARY nvcuvid
          HINTS
          ${CUDAToolkit_LIBRARY_DIR}
          /usr/lib/x86_64-linux-gnu
          /usr/lib64
          ${CUDA_TOOLKIT_ROOT_DIR}/lib64
          ${CUDA_TOOLKIT_ROOT_DIR}/lib/x64
          ${CUDA_TOOLKIT_ROOT_DIR}/lib/Win32
  )
  if(CUDA_NVCUVID_LIBRARY)
    target_link_libraries(decord PRIVATE ${CUDA_NVCUVID_LIBRARY})
    message(STATUS "Found nvcuvid: ${CUDA_NVCUVID_LIBRARY}")
  else()
    message(WARNING "nvcuvid library not found. Hardware video decoding may not work.")
  endif()

  # 6. Set the CUDA standard
  set_property(TARGET decord PROPERTY CUDA_STANDARD 11)
endif()

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
find_package(GTest QUIET)
if(GTest_FOUND)
  enable_testing()
  file(GLOB_RECURSE TEST_SRCS "tests/cpp/*.cc")
  foreach(test_src IN LISTS TEST_SRCS)
    get_filename_component(test_name "${test_src}" NAME_WLE)
    add_executable(${test_name} ${test_src})
    target_link_libraries(${test_name} PRIVATE decord GTest::gtest)
    if(UNIX AND NOT APPLE AND NOT MSVC)
      target_link_libraries(${test_name} PRIVATE pthread dl)
    elseif(APPLE)
      target_link_libraries(${test_name} PRIVATE pthread)
    endif()
    add_test(NAME ${test_name} COMMAND ${test_name})
  endforeach()
  list(LENGTH TEST_SRCS NUM_TESTS)
  message(STATUS "Configured ${NUM_TESTS} C++ unit tests")
endif()

# ---------------------------------------------------------------------------
# Installation
# ---------------------------------------------------------------------------
include(GNUInstallDirs)
install(TARGETS decord
        EXPORT decordTargets
        RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
        LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
        ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR})

install(DIRECTORY include/decord DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
export(EXPORT decordTargets FILE "${CMAKE_CURRENT_BINARY_DIR}/decord-config.cmake")