#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <string.h>
#include "vix.h"

void VixDiscoveryProc(VixHandle jobHandle, VixEventType eventType,
                      VixHandle moreEventInfo, void *clientData)
{
    VixError err = VIX_OK;
    char *url = NULL;

    if (VIX_EVENTTYPE_FIND_ITEM != eventType)
        return;

    err = Vix_GetProperties(moreEventInfo,
                           VIX_PROPERTY_FOUND_ITEM_LOCATION,
                           &url,
                           VIX_PROPERTY_NONE);
    if (VIX_OK != err) goto end;

    printf("\nFound virtual machine: %s\n", url);

    end:
        Vix_FreeBuffer(url);
}

void ListVMs(VixHandle hostHandle)
{
    VixHandle jobHandle;
    VixError err;
    printf("\nLooking for running virtual machines\n");

    jobHandle = VixHost_FindItems(hostHandle, VIX_FIND_RUNNING_VMS,
                                 VIX_INVALID_HANDLE, -1,
                                 VixDiscoveryProc, NULL);
                                 
    err = VixJob_Wait(jobHandle, VIX_PROPERTY_NONE);
        
    if (VIX_OK != err) goto abort;
        
    Vix_ReleaseHandle(jobHandle);
    return;
    
    abort:
        printf("An error occured: Error %d\n", (int)err);
        Vix_ReleaseHandle(jobHandle);
        VixHost_Disconnect(hostHandle);
}

VixHandle ConnectHost(char* hostname, char* user, 
                    char* pass, VixHandle hostHandle)
{
    VixHandle jobHandle;
    VixError err;
    
    jobHandle = VixHost_Connect(VIX_API_VERSION, VIX_SERVICEPROVIDER_DEFAULT,
                            hostname, 0, user, pass, 0, VIX_INVALID_HANDLE,
                            NULL, NULL);
                            
    err = VixJob_Wait(jobHandle, VIX_PROPERTY_JOB_RESULT_HANDLE,
                    &hostHandle, VIX_PROPERTY_NONE);
                        
    if (VIX_OK != err) exit(-1);
    
    Vix_ReleaseHandle(jobHandle);
    printf("Connection Successful\n");
    return hostHandle;
}

void RunProgramInGuest(VixHandle hostHandle, char* path, char* user, 
                        char* pass, char* cmd, char* args)
{
    VixHandle vmHandle;
    VixHandle jobHandle;
    VixError err;
    
    jobHandle = VixVM_Open(hostHandle, path, NULL, NULL);
    
    err =   VixJob_Wait(jobHandle, VIX_PROPERTY_JOB_RESULT_HANDLE,
                        &vmHandle, VIX_PROPERTY_NONE);
                        
    if (VIX_OK != err) goto abort;
    
    Vix_ReleaseHandle(jobHandle);
    
    jobHandle = VixVM_LoginInGuest(vmHandle, user, pass, 0, NULL, NULL);

    err = VixJob_Wait(jobHandle, VIX_PROPERTY_NONE);    
    if (VIX_OK != err) goto abort;
        
    printf("Successfully logged into guest\n");
    Vix_ReleaseHandle(jobHandle);
    
    jobHandle = VixVM_RunProgramInGuest(vmHandle, cmd, args, 
                                        VIX_RUNPROGRAM_RETURN_IMMEDIATELY, 
                                        VIX_INVALID_HANDLE, NULL, NULL);

    err = VixJob_Wait(jobHandle, VIX_PROPERTY_NONE);
    
    if (VIX_OK != err) goto abort;

    Vix_ReleaseHandle(jobHandle);
    
    return;

    abort:
        printf("An error occured: Error %d\n", (int)err);
        Vix_ReleaseHandle(jobHandle);
        Vix_ReleaseHandle(vmHandle);
        VixHost_Disconnect(hostHandle);
        exit(-1);
} 

int main(int argc, char* argv[])
{
    
    VixHandle hostHandle = VIX_INVALID_HANDLE;
    char* hostname;
    char* hostUsername;
    char* hostPassword;
    char* guestPath;
    char* guestUsername;
    char* guestPassword;
    char* hostCommand;
    char* guestCommand;
    char* args = "";
    int c;
    
    while((c = getopt(argc, argv, "h:u:p:g:U:P:c:C:a:")) != -1)
    {
        switch(c)
        {
            case 'h':       hostname = optarg;
                            break;
            
            case 'u':       hostUsername = optarg;
                            break;
    
            case 'p':       hostPassword = optarg;
                            break;
                            
            case 'g':       guestPath = optarg;
                            break;
                            
            case 'U':       guestUsername = optarg;
                            break;
                            
            case 'P':       guestPassword = optarg;
                            break;
                            
            case 'c':       hostCommand = optarg;
                            break;
                            
            case 'C':       guestCommand = optarg;
                            break;
                            
            case 'a':       args = optarg;
                            break;
                            
            default:        printf("Invalid command-line option\n");
                            exit(-1);
        };
    }
    

    hostHandle = ConnectHost(hostname, hostUsername, hostPassword, hostHandle);
    
    if(!strcmp(hostCommand, "ListVMs"))
        ListVMs(hostHandle);
    else if(!strcmp(hostCommand, "RunProgramInGuest"))
        RunProgramInGuest(hostHandle, guestPath, guestUsername, guestPassword, guestCommand, args);    
    return;
}


