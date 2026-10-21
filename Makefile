CC ?= cc
AR ?= ar
CFLAGS ?= -O2 -std=c11 -Wall -Wextra -Werror -Wno-misleading-indentation
INCLUDES = -Isrc
SRC = src/pagezip.c src/pz01.c src/checksum.c
BUILD = build
.PHONY: all test sanitize benchmark clean

all: $(BUILD)/test_codec $(BUILD)/libnano_pz.a

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/%.o: src/%.c | $(BUILD)
	$(CC) $(CFLAGS) $(INCLUDES) -c $< -o $@

$(BUILD)/libnano_pz.a: $(BUILD)/pagezip.o $(BUILD)/pz01.o $(BUILD)/checksum.o
	$(AR) rcs $@ $^

$(BUILD)/test_codec: $(SRC) tests/test_codec.c | $(BUILD)
	$(CC) $(CFLAGS) $(INCLUDES) $(SRC) tests/test_codec.c -o $@

test: $(BUILD)/test_codec
	./$(BUILD)/test_codec

sanitize:
	$(MAKE) clean
	$(MAKE) CFLAGS='-O1 -g -std=c11 -Wall -Wextra -Werror -Wno-misleading-indentation -fsanitize=address,undefined -fno-omit-frame-pointer' test

benchmark: | $(BUILD)
	$(CC) $(CFLAGS) $(INCLUDES) $(SRC) benchmarks/bench.c -o $(BUILD)/bench -lz -llz4 -lzstd
	python3 tools/generate_synthetic.py $(BUILD)/data
	@echo 'Run: ./build/bench pz02 sample build/data/sample.pgs'

clean:
	rm -rf $(BUILD)

.PHONY: example
example: | $(BUILD)
	$(CC) $(CFLAGS) $(INCLUDES) $(SRC) examples/quickstart.c -o $(BUILD)/quickstart
	./$(BUILD)/quickstart
