// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#import <Cocoa/Cocoa.h>
#import "MainWindowController.h"

@interface AppDelegate : NSObject <NSApplicationDelegate>
@property(nonatomic, strong) MainWindowController *mainWindowController;
@end

@implementation AppDelegate

- (void)applicationDidFinishLaunching:(NSNotification *)notification
{
    (void)notification;
    self.mainWindowController = [[MainWindowController alloc] init];
    [self installMenus];
    [self.mainWindowController showWindow:self];
    [NSApp activateIgnoringOtherApps:YES];
}

- (void)installMenus
{
    NSMenu *menuBar = [[NSMenu alloc] initWithTitle:@""];
    NSMenuItem *applicationItem = [[NSMenuItem alloc] initWithTitle:@"FacMan" action:nil keyEquivalent:@""];
    [menuBar addItem:applicationItem];
    NSMenu *applicationMenu = [[NSMenu alloc] initWithTitle:@"FacMan"];
    NSMenuItem *about = [applicationMenu addItemWithTitle:@"About FacMan Preview" action:@selector(showSettingsAbout:) keyEquivalent:@""];
    [about setTarget:self.mainWindowController];
    [applicationMenu addItem:[NSMenuItem separatorItem]];
    NSMenuItem *restore = [applicationMenu addItemWithTitle:@"Restore System Native Appearance" action:@selector(restoreSystemNative:) keyEquivalent:@"0"];
    [restore setTarget:self.mainWindowController];
    [applicationMenu addItem:[NSMenuItem separatorItem]];
    [applicationMenu addItemWithTitle:@"Quit FacMan" action:@selector(terminate:) keyEquivalent:@"q"];
    [applicationItem setSubmenu:applicationMenu];

    NSMenuItem *navigateItem = [[NSMenuItem alloc] initWithTitle:@"Navigate" action:nil keyEquivalent:@""];
    [menuBar addItem:navigateItem];
    NSMenu *navigateMenu = [[NSMenu alloc] initWithTitle:@"Navigate"];
    [navigateMenu addItemWithTitle:@"Instances" action:@selector(showInstances:) keyEquivalent:@"1"];
    [navigateMenu addItemWithTitle:@"Installations" action:@selector(showInstallations:) keyEquivalent:@"2"];
    [navigateMenu addItemWithTitle:@"Activity" action:@selector(showActivity:) keyEquivalent:@"3"];
    [navigateMenu addItemWithTitle:@"Settings / About" action:@selector(showSettingsAbout:) keyEquivalent:@"4"];
    [navigateMenu addItemWithTitle:@"Advanced" action:@selector(showAdvanced:) keyEquivalent:@"5"];
    for (NSMenuItem *item in [navigateMenu itemArray]) [item setTarget:self.mainWindowController];
    [navigateItem setSubmenu:navigateMenu];
    [NSApp setMainMenu:menuBar];
}

- (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSApplication *)sender
{
    (void)sender;
    return YES;
}

@end
