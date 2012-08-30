int 
main(int argc, char * const argv[]) 
{
    unsigned long i = 0;
    __sync_lock_test_and_set(&i, 0);
    __sync_lock_test_and_set(&i, 1);
    __sync_add_and_fetch(&i, argc);
    __sync_sub_and_fetch(&i, argc);
    return 0;
}
