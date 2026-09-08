.PHONY: test test-core test-companion

test: test-core test-companion

test-core:
	mkdir -p build
	g++ -std=c++17 -Wall -Wextra -Werror -Ifirmware firmware/RemoteProtocol.cpp tests/cpp/test_remote_protocol.cpp -o build/test_remote_protocol
	./build/test_remote_protocol
	g++ -std=c++17 -Wall -Wextra -Werror -Ifirmware tests/cpp/test_desktop_tiles.cpp -o build/test_desktop_tiles
	./build/test_desktop_tiles

test-companion:
	PYTHONPATH=companion pytest -q companion/tests
