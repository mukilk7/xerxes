#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <linux/unistd.h>
#include <sys/types.h>
#include <sys/time.h>
#include <sys/sysinfo.h>
#include <time.h>
#include <string.h>
#include <signal.h>
#include <math.h>
#include <pthread.h>
#include "wec.h"
#include "wec_decl.h"
 
/* Globals for values input */
int cpu_wkset_size;
float cpuness;
float ioness;
long loop_length;
char paramfile[MAX_STR_LEN];
int have_config = 0; /* bool */
int num_threads = 0;

/* Globals filled by calibration stage */
float time_per_cpuness_iteration;
float io_scale;

/* Arrays */
int cpuness_array[CPUNESS_INT_ARRAY_SIZE];
int *mem_arr;

/* Piping globals */
int seed = 23;
int p = 0;
int WILEE_RECALIBRATE = 0;
struct timeval pr, ne;
struct timespec t_val;
struct sigaction act;

/* Execution threads */
pthread_t threads[MAX_THREADS];

/* Integer division should suffice */
#define BYTES_TO_MBYTES(m) (m / (1024.0f * 1024.0f))

int interval_rand(int low_rand, int high_rand)
{
    int r = rand_r(&seed) % high_rand;
	return r < low_rand? (low_rand + r) % high_rand : r;
}

long timeval_diff(struct timeval* p, struct timeval* n)
{
	return 1000000 * (n->tv_sec - p->tv_sec) +
        n->tv_usec - p->tv_usec;
}

/*
 * Find out how many operations correspond to 100% of CPU-ness
 * respectively.
 */
void calibrate()
{
	int retval;
	cpu_calibrate();
	sleep_calibrate();
}

int cpu_inner_loop(long cal, int p)
{
	int i, j, k, tmp, jnk = 0;
	long sum;
	for (j = 0; j < cal; j++) {
		sum = 0;
		for (i = 0; i< CPUNESS_INT_ARRAY_SIZE; i++) {
			tmp = 1;
			for (k = 0; k < p; k++)
				tmp *= cpuness_array[i];
			sum += tmp;		
		}
		if (sum % 2 && sum % 3)
			jnk++;
	}
	return jnk;
}

void cpu_calibrate()
{
	int i;
    // Limits for interval_rand()
	int lr = 0, hr= 1000;
    // No of loops to calibrate with.
	int calib_length = CPU_CALIBRATION_LOOPS;
    // No of loops needed to achieve loop_length
	long long calib_loops;
	for (i = 0; i < CPUNESS_INT_ARRAY_SIZE; i++) {
		cpuness_array[i] = interval_rand(lr, hr);
	}
	p = interval_rand(0,4);
        
    /* 
     * Calibrate by checking how long it takes to run calib_length number of
     * loops.
     */
	gettimeofday(&pr, NULL);
	cpu_inner_loop(calib_length, p);
	gettimeofday(&ne, NULL);
	time_per_cpuness_iteration = (float)(timeval_diff(&pr, &ne))
        / (float)calib_length;
	calib_loops = loop_length / time_per_cpuness_iteration;
}

void sleep_calibrate()
{
	int i, min_gr = 1000;
	float sc;
    
	for (i = 1; i <= 100; i+=10) {
		gettimeofday(&pr, NULL);
		usleep(i * min_gr);
		gettimeofday(&ne, NULL);
		sc = (float)(timeval_diff(&pr, &ne)) / (float)(i * min_gr);
	}
	io_scale = sc;
}

int process_input(int argc, char* argv[])
{
	int n = argc, i;
    loop_length = WEC_MINIMUM_LOOP_GRANULARITY;    
    /* Assume single-core by default */
    num_threads = 1; 
    
	while (n > 1) {

        if (!strcmp(argv[argc - n + 1], "-l") ||
            !strcmp(argv[argc - n + 1], "--loop_length")) {
            
			loop_length = atoi(argv[argc - n + 2]);
			if (loop_length < WEC_MINIMUM_LOOP_GRANULARITY) {
				fprintf(stderr, "Setting loop granularity to %d\n", 
                        WEC_MINIMUM_LOOP_GRANULARITY);
				loop_length = WEC_MINIMUM_LOOP_GRANULARITY;
			}
			n -= 2;
		}
        else if (!strcmp(argv[argc - n + 1], "-f")) {

			strcpy(paramfile, argv[argc - n + 2]);
            if (strlen(paramfile) <= 0) {
                fprintf(stderr, "INVALID CONFIG FILE.\n");
                return -1;
            }
            have_config = 1;
            n -= 2;
		}
        else if (!strcmp(argv[argc - n + 1], "-t")) {
            num_threads = atoi(argv[argc - n + 2]);
            n -= 2;
		}
        else if (!strcmp(argv[argc - n + 1], "--recalibrate")) {
            WILEE_RECALIBRATE = 1;
            n -= 2;
        }
	}

    if (have_config > 0) {
        return 0;
    } else {
        return -1;
    }
}


/*
 * Actually run the loops after calibration values have been either supplied
 * or calculated.
 */
void do_loops(void *ptr)
{
	int i, j;
	float cpu_length, io_length;
	int cpu_loops;

	cpu_length = loop_length * cpuness;
	cpu_loops = cpu_length / time_per_cpuness_iteration;
    io_length = loop_length * ioness;

    while (1) {

        /* To Quit on timer */
        pthread_testcancel();

		cpu_inner_loop(cpu_loops, p);
		if (io_length)
			usleep((int)(io_length / io_scale));		
	}

    pthread_exit(0);
}

void alloc_memory(int memsizemb)
{
    long arr_size = (long)((memsizemb*1024*1024)/sizeof(int));    
    long k = 0;

    mem_arr = (int*)malloc(arr_size * sizeof(int));

    if (NULL == mem_arr) {
        printf("Memory Allocation Failed for Size %d MB\n", memsizemb);
        exit(1);
    }

    /* Molest Allocated Memory */
    for (k = 0; k < arr_size; k++) {
        mem_arr[k] = k;
    }
}

void free_memory()
{
    if (mem_arr != NULL) {
        free(mem_arr);
        mem_arr = NULL;
    }
}

void timer_alarm_handler(int sig)
{
    int i = 0;
    for (i = 0; i < num_threads; i++) {
        pthread_cancel(threads[i]);
    }
    signal(SIGALRM, timer_alarm_handler);
}

int main(int argc, char *argv[])
{
    FILE *config;
    int curperiodsecs = 0;
    int cpuloadpct = 0, memsizepct = 0;
    int i = 0, memsizemb = 0;
    struct sysinfo si;

    signal(SIGALRM, timer_alarm_handler);
    sysinfo(&si);
    
	if (process_input(argc,argv) < 0) {
        printf("ERROR: Insufficient input parameters\n");
		exit(1);
	}

    config = fopen(paramfile, "r");
    if (!config) {
        printf("Unable to Open Param File\n");
        exit(1);
    }

    if (!WILEE_RECALIBRATE) {
        calibrate();
    }
    
    while(!feof(config)) {            
        
        if (fscanf(config, "%d\t%d\t%d", &curperiodsecs,
                   &cpuloadpct, &memsizepct) < 3) {
            continue;
        }

        if (WILEE_RECALIBRATE) {
            calibrate();
        }
        
        memsizemb = (int) (((float)memsizepct/100.0f) *
                           BYTES_TO_MBYTES(si.totalram));
        cpuness = ((float)cpuloadpct/100.0f);
        ioness = 1.0 - cpuness;

        /*
        printf("CPU load pct : %f Threads = %d MemMB = %d for %d seconds\n",
               cpuness, num_threads, memsizemb, curperiodsecs);
        */

        for (i = 0; i < num_threads; i++) {
            pthread_create(&threads[i], NULL, (void *) &do_loops, NULL);
        }
        
        alarm(curperiodsecs);
        
        alloc_memory(memsizemb);
        
        for (i = 0; i < num_threads; i++) {
            pthread_join(threads[i], NULL);
        }            
        
        free_memory();
    }
}	
