CC ?= cc
AR ?= ar
CFLAGS ?= -O2 -std=c11 -Wall -Wextra -Werror -Wno-misleading-indentation
INCLUDES = -Isrc
SRC = models/pz/pagezip.c models/pz/pz01.c src/checksum.c models/pz/pz03_page.c src/predictor.c models/pza/pza.c
BUILD = build
OBJECTS = $(SRC:%.c=$(BUILD)/%.o)
PIC_OBJECTS = $(SRC:%.c=$(BUILD)/pic/%.o)
PAGE_TESTS = test_codec test_pz03_page test_pza test_pza_transform_bounds test_page_wire_bounds
TEST_OBJECTS = $(addprefix $(BUILD)/tests/,$(addsuffix .o,$(PAGE_TESTS)))
EXEEXT := $(if $(filter Windows_NT,$(OS)),.exe,)
TEST_BINARIES = $(addprefix $(BUILD)/,$(addsuffix $(EXEEXT),$(PAGE_TESTS)))
HOST_OBJECTS = $(BUILD)/experimental/native/solid_native.o $(BUILD)/tests/io_faults.o $(BUILD)/benchmarks/baseline/solid_native-v010.o $(BUILD)/benchmarks/baseline/solid_native-v011.o
DEPS = $(OBJECTS:.o=.d) $(PIC_OBJECTS:.o=.d) $(TEST_OBJECTS:.o=.d) $(BUILD)/examples/quickstart.d $(HOST_OBJECTS:.o=.d)
.DEFAULT_GOAL := all
.PHONY: all test sanitize benchmark clean

all: $(BUILD)/test_codec$(EXEEXT) $(BUILD)/libnano_pz.a

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/%.o: %.c
	mkdir -p $(@D)
	$(CC) $(CFLAGS) $(INCLUDES) -MMD -MP -MF $(@:.o=.d) -c $< -o $@

$(BUILD)/pic/%.o: %.c
	mkdir -p $(@D)
	$(CC) $(CFLAGS) $(INCLUDES) -fPIC -MMD -MP -MF $(@:.o=.d) -c $< -o $@

$(BUILD)/libnano_pz.a: $(OBJECTS)
	$(AR) rcs $@ $^

$(BUILD)/test_codec$(EXEEXT): $(OBJECTS) $(BUILD)/tests/test_codec.o
	$(CC) $(CFLAGS) $^ -o $@

test: test-pages

sanitize: | $(BUILD)
	$(CC) -O1 -g -std=c11 -fsanitize=address,undefined -fno-omit-frame-pointer $(INCLUDES) $(SRC) tests/test_codec.c -o $(BUILD)/codec-sanitize
	ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 ./$(BUILD)/codec-sanitize
	$(CC) -O1 -g -std=c11 -fsanitize=address,undefined -fno-omit-frame-pointer $(INCLUDES) $(SRC) tests/test_pz03_page.c -o $(BUILD)/pz03-sanitize
	ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 ./$(BUILD)/pz03-sanitize

	$(CC) -O1 -g -std=c11 -fsanitize=address,undefined -fno-omit-frame-pointer $(INCLUDES) $(SRC) tests/test_pza.c -o $(BUILD)/pza-sanitize
	ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 ./$(BUILD)/pza-sanitize
	$(CC) -O1 -g -std=c11 -fsanitize=address,undefined -fno-omit-frame-pointer $(INCLUDES) $(SRC) tests/test_pza_transform_bounds.c -o $(BUILD)/pza-transform-sanitize
	ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 ./$(BUILD)/pza-transform-sanitize
	$(CC) -O1 -g -std=c11 -fsanitize=address,undefined -fno-omit-frame-pointer $(INCLUDES) $(SRC) tests/test_page_wire_bounds.c -o $(BUILD)/page-wire-sanitize
	ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 ./$(BUILD)/page-wire-sanitize

benchmark: | $(BUILD)
	python3 tools/bench_pages.py $(BENCH_ARGS)

clean:
	rm -rf $(BUILD)

.PHONY: example
example: $(BUILD)/quickstart$(EXEEXT)
	./$(BUILD)/quickstart$(EXEEXT)

$(BUILD)/quickstart$(EXEEXT): $(OBJECTS) $(BUILD)/examples/quickstart.o
	$(CC) $(CFLAGS) $^ -o $@

# PZ03 envelope is opt-in; historic PZ01/PZ02 format remains compatible.
$(BUILD)/test_pz03_page$(EXEEXT): $(OBJECTS) $(BUILD)/tests/test_pz03_page.o
	$(CC) $(CFLAGS) $^ -o $@

$(BUILD)/libnano_pz.so: $(PIC_OBJECTS)
	$(CC) $(CFLAGS) -shared -fPIC $^ -o $@

$(BUILD)/solid-native: $(BUILD)/experimental/native/solid_native.o $(BUILD)/src/predictor.o
	$(CC) $(CFLAGS) $^ -o $@ -lz -lcrypto

.PHONY: test-pages test-host sanitize-host test-jury
test-pages: $(TEST_BINARIES)
	./$(BUILD)/test_codec$(EXEEXT)
	./$(BUILD)/test_pz03_page$(EXEEXT)
	./$(BUILD)/test_pza$(EXEEXT)
	./$(BUILD)/test_pza_transform_bounds$(EXEEXT)
	./$(BUILD)/test_page_wire_bounds$(EXEEXT)

$(BUILD)/test_pza_transform_bounds$(EXEEXT): $(OBJECTS) $(BUILD)/tests/test_pza_transform_bounds.o
	$(CC) $(CFLAGS) $^ -o $@

$(BUILD)/test_page_wire_bounds$(EXEEXT): $(OBJECTS) $(BUILD)/tests/test_page_wire_bounds.o
	$(CC) $(CFLAGS) $^ -o $@

$(BUILD)/test_pza$(EXEEXT): $(OBJECTS) $(BUILD)/tests/test_pza.o
	$(CC) $(CFLAGS) $^ -o $@

test-host: $(BUILD)/solid-native $(BUILD)/libnano_pz.so
	python3 -m unittest discover -s experimental/udict/tests -p 'test_*.py'
	python3 tests/test_solid.py
	python3 tests/test_native_solid.py
	python3 tests/test_pza_assets.py

sanitize-host: $(BUILD)/solid-native-v011 $(BUILD)/libnano_pz.so | $(BUILD)
	$(CC) -O1 -g -std=c11 -fsanitize=address,undefined -fno-omit-frame-pointer experimental/native/solid_native.c src/predictor.c -o $(BUILD)/solid-native-sanitize -lz -lcrypto
	PZ_NATIVE_TEST_BINARY="$(CURDIR)/$(BUILD)/solid-native-sanitize" ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 python3 tests/test_native_solid.py
	PZ_NATIVE_TEST_BINARY="$(CURDIR)/$(BUILD)/solid-native-sanitize" ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 python3 tests/test_jury.py
	PZ_NATIVE_TEST_BINARY="$(CURDIR)/$(BUILD)/solid-native-sanitize" ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 python3 tests/test_router.py
	$(CC) -O1 -g -std=c11 -fsanitize=address,undefined -fno-omit-frame-pointer experimental/native/solid_native.c src/predictor.c tests/io_faults.c -o $(BUILD)/solid-io-sanitize -lz -lcrypto -Wl,--wrap=fwrite,--wrap=write,--wrap=fsync,--wrap=linkat,--wrap=syscall
	PZ_IO_TEST_BINARY="$(CURDIR)/$(BUILD)/solid-io-sanitize" ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 python3 tests/test_io_faults.py

$(BUILD)/solid-io-test: $(BUILD)/experimental/native/solid_native.o $(BUILD)/src/predictor.o $(BUILD)/tests/io_faults.o
	$(CC) $(CFLAGS) $^ -o $@ -lz -lcrypto -Wl,--wrap=fwrite,--wrap=write,--wrap=fsync,--wrap=linkat,--wrap=syscall

test-jury: $(BUILD)/solid-native $(BUILD)/solid-io-test $(BUILD)/solid-io-v010 $(BUILD)/solid-native-v011 $(BUILD)/libnano_pz.so
	python3 tests/test_jury.py
	python3 tests/test_io_faults.py
	python3 tools/reproduce_publish.py
	python3 tests/test_router.py

$(BUILD)/solid-native-v011: $(BUILD)/benchmarks/baseline/solid_native-v011.o $(BUILD)/src/predictor.o
	$(CC) $(CFLAGS) $^ -o $@ -lz -lcrypto

$(BUILD)/solid-io-v010: $(BUILD)/benchmarks/baseline/solid_native-v010.o $(BUILD)/src/predictor.o $(BUILD)/tests/io_faults.o
	$(CC) $(CFLAGS) $^ -o $@ -lz -lcrypto -Wl,--wrap=fwrite,--wrap=write,--wrap=fsync,--wrap=linkat,--wrap=syscall

# Track actual Windows executables while preserving extensionless make targets.
ifneq ($(EXEEXT),)
.PHONY: $(addprefix $(BUILD)/,$(PAGE_TESTS)) $(BUILD)/quickstart
$(addprefix $(BUILD)/,$(PAGE_TESTS)) $(BUILD)/quickstart: %: %$(EXEEXT)
endif

PYTHON ?= python3
.PHONY: test-build
test-build:
	$(PYTHON) tests/test_build_dependencies.py --make "$(MAKE)" --cc "$(CC)" --ar "$(AR)" --shell "$(SHELL)"

-include $(DEPS)
