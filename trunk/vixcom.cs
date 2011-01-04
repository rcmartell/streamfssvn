using System;
using System.Collections.Generic;
using System.Text;
using System.Runtime.InteropServices;

using VixCOM;

namespace Tranxition.BuildTasks
{
    class VixWrapper
    {
        VixCOM.IVixLib vixLib = null;

        ulong m_vixError;
        VixCOM.IHost m_hostHandle = null;
        VixCOM.IVM m_vmHandle = null;

        public ulong GetError()
        {
            return m_vixError;
        }

        public VixWrapper()
        {
            try
            {
                vixLib = new VixCOM.VixLibClass();
            }
            catch (COMException comExc)
            {
                System.Diagnostics.Trace.WriteLine(comExc.Message + Åg\nÅh);
                throw;
            }
        }

        /// <summary>
        /// Creates a host handle
        /// </summary>
        /// <returns>true if succeeded, otherwise false</returns>
        public bool Connect(string hostName, string userName, string password)
        {
            int hostType = string.IsNullOrEmpty(hostName) ?
                VixCOM.Constants.VIX_SERVICEPROVIDER_VMWARE_WORKSTATION :
                VixCOM.Constants.VIX_SERVICEPROVIDER_VMWARE_SERVER;

            int vixVersion = VixCOM.Constants.VIX_API_VERSION;

            vixVersion = 1; // Bugfix: http://communities.vmware.com/message/649925#649925

            VixCOM.IJob jobHandle = vixLib.Connect(vixVersion,
                hostType, hostName, 0, userName, password, 0, null,  null);

            int[] propertyIds = new int[1] { VixCOM.Constants.VIX_PROPERTY_JOB_RESULT_HANDLE };
            object results = new object();

            m_vixError = jobHandle.Wait(propertyIds, ref results);

            if (m_vixError == VixCOM.Constants.VIX_OK)
            {
                object[] objectArray = (object[])results;
                m_hostHandle = (VixCOM.IHost)objectArray[0];
                return true;
            }

            return false;
        }

        /// <summary>
        /// Opens the virtual machine specified in vmxFilePath
        /// </summary>
        /// <param name=ÅhvmxFilePathÅh>The virtual machine vmx file to open</param>
        /// <returns>true if succeeded, otherwise false</returns>
        public bool Open(string vmxFilePath)
        {
            IJob jobHandle = m_hostHandle.OpenVM(vmxFilePath, null);

            int[] propertyIds = new int[1] { VixCOM.Constants.VIX_PROPERTY_JOB_RESULT_HANDLE };
            object results = new object();

            m_vixError = jobHandle.Wait(propertyIds, ref results);

            if (m_vixError == VixCOM.Constants.VIX_OK)
            {
                object[] objectArray = (object[])results;
                m_vmHandle = (VixCOM.IVM)objectArray[0];
                return true;
            }

            return false;
        }

        /// <summary>
        /// Power on the virtual machine
        /// </summary>
        /// <returns>true if succeeded, otherwise false</returns>
        public bool PowerOn()
        {
            IJob jobHandle = m_vmHandle.PowerOn(VixCOM.Constants.VIX_VMPOWEROP_LAUNCH_GUI,
                null, null);
            m_vixError = jobHandle.WaitWithoutResults();

            if (m_vixError == VixCOM.Constants.VIX_OK)
            {
                //
                // Wait until guest is completely booted.
                //
                jobHandle = m_vmHandle.WaitForToolsInGuest(300, null);

                m_vixError = jobHandle.WaitWithoutResults();
            }

            return (m_vixError == VixCOM.Constants.VIX_OK);
        }

        /// <summary>
        /// Starts a snapshot of a virtual machine
        /// </summary>
        /// <param name=Åhsnapshot_nameÅh>The name of the snapshot to start</param>
        /// <returns>true if succeeded, otherwise false</returns>
        public bool RevertToLastSnapshot()
        {
            ISnapshot snapshot = null;
            m_vixError = m_vmHandle.GetRootSnapshot(0, out snapshot);

            if (m_vixError == VixCOM.Constants.VIX_OK)
            {
                IJob jobHandle = m_vmHandle.RevertToSnapshot(snapshot, 0, null, null);

                m_vixError = jobHandle.WaitWithoutResults();
            }

            return (m_vixError == VixCOM.Constants.VIX_OK);
        }

        /// <summary>
        /// Login to the virtual machine
        /// </summary>
        /// <returns>true if succeeded, otherwise false</returns>
        public bool LogIn(string username, string password)
        {
            IJob jobHandle = m_vmHandle.LoginInGuest(username, password, 0, null);
            m_vixError = jobHandle.WaitWithoutResults();

            return (m_vixError == VixCOM.Constants.VIX_OK);
        }

        /// <summary>
        /// Creates the directory in the Virtual Machine
        /// </summary>
        /// <param name=ÅhpathNameÅh></param>
        /// <returns></returns>
        public bool CreateDirectoryInVm(string pathName)
        {
            IJob jobHandle = m_vmHandle.CreateDirectoryInGuest(pathName, null, null);
            m_vixError = jobHandle.WaitWithoutResults();

            return (m_vixError == VixCOM.Constants.VIX_OK);
        }

        /// <summary>
        /// Copies a file from the host machine to the virtual machine
        /// </summary>
        /// <param name=ÅhsourceFileÅh>The source file on the host machine</param>
        /// <param name=ÅhdestinationFileÅh>The destination on the VM</param>
        /// <returns>true if succeeded, otherwise false</returns>
        public bool CopyFileToVm(string sourceFile, string destinationFile)
        {
            //
            // Copy files from host to guest
            //
            IJob jobHandle = m_vmHandle.CopyFileFromHostToGuest(sourceFile, destinationFile,
                0, null, null);
            m_vixError = jobHandle.WaitWithoutResults();

            return (m_vixError == VixCOM.Constants.VIX_OK);
        }

        /// <summary>
        /// Copies a file from the virtual machine to the host machine
        /// </summary>
        /// <param name=ÅhsourceFileÅh>The source file on the virtual machine</param>
        /// <param name=ÅhdestinationFileÅh>The destination on the host machine</param>
        /// <returns>true if succeeded, otherwise false</returns>
        public bool CopyFileFromVm(string sourceFile, string destinationFile)
        {
            //
            // Copy files from host to guest
            //
            IJob jobHandle = m_vmHandle.CopyFileFromGuestToHost(sourceFile, destinationFile,
                0, null, null);
            m_vixError = jobHandle.WaitWithoutResults();

            return (m_vixError == VixCOM.Constants.VIX_OK);
        }

        /// <summary>
        /// Runs a program on the virtual machine
        /// </summary>
        /// <param name=ÅhexePathÅh>The path of the program on the virtual machine</param>
        /// <param name=ÅhparametersÅh>The parameters to pass to the executable</param>
        /// <param name=ÅhresultCodeÅh>The result code returned from the program that ran on the VM</param>
        /// <returns>true if succeeded, otherwise false</returns>
        public bool RunProgram(string exePath, string parameters, out int resultCode)
        {
            resultCode = -1;

            IJob jobHandle = m_vmHandle.RunProgramInGuest(exePath,
                parameters, VixCOM.Constants.VIX_RUNPROGRAM_ACTIVATE_WINDOW, null, null); // clientData

            int[] propertyIds = new int[1] { VixCOM.Constants.VIX_PROPERTY_JOB_RESULT_GUEST_PROGRAM_EXIT_CODE };
            object results = new object();
            m_vixError = jobHandle.Wait(propertyIds, ref results);

            if (m_vixError == VixCOM.Constants.VIX_OK)
            {
                object[] objectArray = (object[])results;
                resultCode = (int)objectArray[0];
                return true;
            }

            return false;
        }

        /// <summary>
        /// Power off the virtual machine
        /// </summary>
        /// <returns>true if succeeded, otherwise false</returns>
        public bool PowerOff()
        {
            IJob jobHandle = m_vmHandle.PowerOff(VixCOM.Constants.VIX_VMPOWEROP_NORMAL, null);
            m_vixError = jobHandle.WaitWithoutResults();

            return (m_vixError == VixCOM.Constants.VIX_OK);
        }
    }
}
Gotchas

After figuring everything out, I only ran into one glitch. You may have noticed the following lines in the code:

int vixVersion = VixCOM.Constants.VIX_API_VERSION;
vixVersion = 1; // Bugfix: http://communities.vmware.com/message/649925#649925

VixCOM.Constants.VIX_API_VERSION seems like the correct value to use for the Connect method, but it does cause an error. I did find the solution in the VMWare support message board.

The RunProgram function will return true or false, depending on if the program successfully executed. It has nothing to do with the return value of the program. The resultCode is the return value of the application.
Using the class

The only exception that should get thrown using this code is a COMException, so this is the only exception type that I catch. This will definitely occur if the VixCOM dll is not registered on the system. Here is a simple example of how to use the class:

try
{
    VixWrapper vix = new VixWrapper();

    //
    // Connect to the VMWare Server
    //
    if (vix.Connect(hostName, hostUser, hostPassword))
    {
        //
        // Opening the VMX File
        //
        if (vix.Open(vmxFilePath))
        {
            //
            // Reverting to the ÅeonlyÅf snapshot
            //
            if (vix.RevertToLastSnapshot())
            {
                //
                // Powering on the Virtual Machine
                //
                if (vix.PowerOn())
                {
                    //
                    // Logging in to the Virtual Machine
                    //
                    if (vix.LogIn(virtualMachineUsername, virtualMachinePassword))
                    {
                        //
                        // Copy the files to the virtual machine
                        //
                        bool copiedFilesSuccessfully = true;
                        foreach (ITaskItem fileToCopy in filesToCopy)
                        {
                            string sourceFilePath = fileToCopy.ItemSpec;

                            //
                            // The file must exist.
                            //
                            if (!File.Exists(sourceFilePath))
                            {
                                copiedFilesSuccessfully = false;
                                break;
                            }

                            string destinationFilePath = Path.Combine(virtualMachinePath, Path.GetFileName(sourceFilePath));

                            //
                            // Copying in files to the Virtual Machine
                            //
                            if (!vix.CopyFileToVm(sourceFilePath, destinationFilePath))
                            {
                                copiedFilesSuccessfully = false;
                                break;
                            }
                        }

                        //
                        // If we didnÅft fail to copy any files over, then run the test
                        //
                        if (copiedFilesSuccessfully)
                        {
                            //
                            // Run the test program
                            //
                            int resultCode = 0;
                            if (vix.RunProgram(exePath, exeParameters, out resultCode))
                            {
                                if (resultCode == 0)
                                {
                                    //
                                    // The test PASSED!
                                    //
                                    returnValue = true;
                                }
                                else
                                {
                                    // The test FAILED!
                                    returnValue = false;
                                }
                            }
                            else
                            {
                                //
                                // Unable to run test
                                //
                            }
                        }
                    }
                    else
                    {
                        // Unable to login to the virtual machine
                    }

                    vix.PowerOff();
                }
                else
                {
                    // Unable to power on the virtual machine
                }
            }
            else
            {
                // Unable to revert to the last snapshot
            }
        }
        else
        {
            // Unable to open the VMX file
        }
    }
    else
    {
        // Unable to connect to the host
    }

    return returnValue;
}
catch (COMException comExc)
{
    //
    // COM Exception
    //
    return false;
}