CC=gcc
CFLAGS=-Wall
OUT=wileE

wileE: loops.c wec.h wec_decl.h
	$(CC) -lm -lpthread loops.c -o $(OUT)
clean:
	rm -f wileE
