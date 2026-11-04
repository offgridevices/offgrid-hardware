# Host tests of the port logic (no board needed):  make -C firmware/test
SRC = ../lib/hub/src/hub.cpp ../lib/hub/src/cmd.cpp test_hub.cpp
CXXFLAGS = -std=c++17 -Wall -Wextra -Werror -O1 -g -fsanitize=address,undefined

test: $(SRC) ../lib/hub/src/hub.h ../lib/hub/src/cmd.h
	$(CXX) $(CXXFLAGS) -o /tmp/print-hub-test $(SRC)
	/tmp/print-hub-test

.PHONY: test
