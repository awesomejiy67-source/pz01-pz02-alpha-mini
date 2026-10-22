CC ?= cc
AR ?= ar
CFLAGS ?= -O2 -std=c11 -Wall -Wextra -Werror -Wno-misleading-indentation
INCLUDES = -Isrc
SRC = src/pagezip.c src/pz01.c src/checksum.c src/pz03_page.c src/predictor.c
BUILD = build
.PHONY: all test sanitize benchmark clean

all: $(BUILD)/test_codec $(BUILD)/libnano_pz.a

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/%.o: src/%.c | $(BUILD)
	$(CC) $(CFLAGS) $(INCLUDES) -c $< -o $@

$(BUILD)/libnano_pz.a: $(BUILD)/pagezip.o $(BUILD)/pz01.o $(BUILD)/checksum.o $(BUILD)/pz03_page.o $(BUILD)/predictor.o
	$(AR) rcs $@ $^

$(BUILD)/test_codec: $(SRC) tests/test_codec.c | $(BUILD)
	$(CC) $(CFLAGS) $(INCLUDES) $(SRC) tests/test_codec.c -o $@

test: test-pages

sanitize: | $(BUILD)
	$(CC) -O1 -g -std=c11 -fsanitize=address,undefined -fno-omit-frame-pointer $(INCLUDES) $(SRC) tests/test_codec.c -o $(BUILD)/codec-sanitize
	ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 ./$(BUILD)/codec-sanitize
	$(CC) -O1 -g -std=c11 -fsanitize=address,undefined -fno-omit-frame-pointer $(INCLUDES) $(SRC) tests/test_pz03_page.c -o $(BUILD)/pz03-sanitize
	ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 ./$(BUILD)/pz03-sanitize

benchmark: | $(BUILD)
	python3 tools/bench_pages.py $(BENCH_ARGS)

clean:
	rm -rf $(BUILD)

.PHONY: example
example: | $(BUILD)
	$(CC) $(CFLAGS) $(INCLUDES) $(SRC) examples/quickstart.c -o $(BUILD)/quickstart
	./$(BUILD)/quickstart

# PZ03 envelope is opt-in; historic PZ01/PZ02 format remains compatible.
$(BUILD)/test_pz03_page: $(SRC) tests/test_pz03_page.c | $(BUILD)
	$(CC) $(CFLAGS) $(INCLUDES) $(SRC) tests/test_pz03_page.c -o $@

$(BUILD)/libnano_pz.so: $(SRC) | $(BUILD)
	$(CC) $(CFLAGS) $(INCLUDES) -shared -fPIC $(SRC) -o $@

$(BUILD)/solid-native: experimental/native/solid_native.c src/predictor.c | $(BUILD)
	$(CC) $(CFLAGS) $^ -o $@ -lz -lcrypto

.PHONY: test-pages test-host sanitize-host test-jury
test-pages: $(BUILD)/test_codec $(BUILD)/test_pz03_page
	./$(BUILD)/test_codec
	./$(BUILD)/test_pz03_page

test-host: $(BUILD)/solid-native $(BUILD)/libnano_pz.so
	python3 -m unittest discover -s experimental/udict/tests -p 'test_*.py'
	python3 tests/test_solid.py
	python3 tests/test_native_solid.py

sanitize-host: $(BUILD)/solid-native-v011 $(BUILD)/libnano_pz.so | $(BUILD)
	$(CC) -O1 -g -std=c11 -fsanitize=address,undefined -fno-omit-frame-pointer experimental/native/solid_native.c src/predictor.c -o $(BUILD)/solid-native-sanitize -lz -lcrypto
	PZ_NATIVE_TEST_BINARY="$(CURDIR)/$(BUILD)/solid-native-sanitize" ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 python3 tests/test_native_solid.py
	PZ_NATIVE_TEST_BINARY="$(CURDIR)/$(BUILD)/solid-native-sanitize" ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 python3 tests/test_jury.py
	PZ_NATIVE_TEST_BINARY="$(CURDIR)/$(BUILD)/solid-native-sanitize" ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 python3 tests/test_router.py
	$(CC) -O1 -g -std=c11 -fsanitize=address,undefined -fno-omit-frame-pointer experimental/native/solid_native.c src/predictor.c tests/io_faults.c -o $(BUILD)/solid-io-sanitize -lz -lcrypto -Wl,--wrap=fwrite,--wrap=write,--wrap=fsync,--wrap=linkat,--wrap=syscall
	PZ_IO_TEST_BINARY="$(CURDIR)/$(BUILD)/solid-io-sanitize" ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 python3 tests/test_io_faults.py

$(BUILD)/solid-io-test: experimental/native/solid_native.c src/predictor.c tests/io_faults.c | $(BUILD)
	$(CC) $(CFLAGS) $^ -o $@ -lz -lcrypto -Wl,--wrap=fwrite,--wrap=write,--wrap=fsync,--wrap=linkat,--wrap=syscall

test-jury: $(BUILD)/solid-native $(BUILD)/solid-io-test $(BUILD)/solid-io-v010 $(BUILD)/solid-native-v011 $(BUILD)/libnano_pz.so
	python3 tests/test_jury.py
	python3 tests/test_io_faults.py
	python3 tools/reproduce_publish.py
	python3 tests/test_router.py

$(BUILD)/solid-native-v011: benchmarks/baseline/solid_native-v011.c src/predictor.c | $(BUILD)
	$(CC) $(CFLAGS) $^ -o $@ -lz -lcrypto

$(BUILD)/solid-io-v010: benchmarks/baseline/solid_native-v010.c src/predictor.c tests/io_faults.c | $(BUILD)
	$(CC) $(CFLAGS) $^ -o $@ -lz -lcrypto -Wl,--wrap=fwrite,--wrap=write,--wrap=fsync,--wrap=linkat,--wrap=syscall
